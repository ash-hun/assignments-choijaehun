"""토크나이저 선정 실험 진입점. 청크 길이 단위 측정과 BM25 토크나이저 비교를 조립하고 결과를 저장한다."""
import sys
import json
import asyncio
import argparse
import tiktoken
from qdrant_client import AsyncQdrantClient

from app.service.eval.tokenizer_benchmark import SparseRun, UnitLength, CharLimitCheck, TokenizerBenchmark
from app.service.eval.tokenizer_benchmark import check_char_limit, measure_units
from app.repository.qdrant_chunk_repository import QdrantChunkRepository
from app.cli.embedding_selection_cli import CANDIDATES, load_gold
from app.service.ingest.chunk_splitter import FixedLengthSplitter
from app.common.text_tokenizer import SplitMode, TextTokenizer
from app.service.ingest.document_loader import load_documents
from app.service.eval.retrieval_metric import paired_against
from app.service.ingest.sparse_encoder import SparseEncoder
from app.client.embedding_client import EmbeddingClient
from app.common.settings import Settings, get_settings
from app.schema.corpus_schema import CorpusManifest
from app.schema.chunk_schema import Chunk
from app.common.logger import get_logger

OUTPUT_DIR = "artifacts/tokenizer"
SELECTED_EMBEDDING = "Qwen/Qwen3-Embedding-0.6B"
RUNNER_UP_EMBEDDING = "intfloat/multilingual-e5-large"
RUNNER_UP_CAP = 512
WINDOWS = (500, 1000, 2000, 4000)
TARGETS = (256, 512, 1024)
SPARSE_CHUNK_CHARS = 1000
# 단순한 순서. 주 지표가 같으면 앞쪽을 고른다.
SPARSE_CANDIDATES = [
    TextTokenizer("whitespace"),
    TextTokenizer("word"),
    TextTokenizer("word", stem=True),
    TextTokenizer("word", stem=True, identifiers=True),
]
# 형태소 분석기는 korean 의존성 그룹이 있는 이미지(batch-korean)에서만 만든다. 단순성은 pip만 필요한 kiwi가 JVM이 필요한 okt, kkma보다 앞선다.
ANALYZER_CANDIDATES: tuple[SplitMode, ...] = ("kiwi", "okt", "kkma")

logger = get_logger(__name__)


def load_chunks(settings: Settings, max_chars: int) -> list[Chunk]:
    """Corpus를 고정 문자 길이로 자른다. 같은 입력이면 같은 청크가 나온다."""
    manifest_path = settings.data_dir / "corpus" / "manifests" / f"{settings.corpus_name}.json"
    manifest = CorpusManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    documents = load_documents(manifest, settings.data_dir / "corpus" / "raw" / settings.corpus_name)
    splitter = FixedLengthSplitter(max_chars)
    return [c for d in documents for c in splitter.split(d)]


def measure_lengths(settings: Settings) -> tuple[list[UnitLength], list[CharLimitCheck]]:
    """분할 크기마다 단위별 길이를 재고, 목표 토큰 수를 문자 수 상한으로 맞출 때 넘치는 비율을 잰다."""
    clients = {
        c.name: EmbeddingClient(c.name, settings.model_cache_dir, c.query_prefix, c.document_prefix)
        for c in CANDIDATES if c.name in (SELECTED_EMBEDDING, RUNNER_UP_EMBEDDING)
    }
    encoding = tiktoken.get_encoding("o200k_base")
    counters = {
        "chars": len,
        "tiktoken_o200k": lambda t: len(encoding.encode(t, disallowed_special=())),
        "qwen3": clients[SELECTED_EMBEDDING].token_count,
        "e5": clients[RUNNER_UP_EMBEDDING].token_count,
    }
    units: list[UnitLength] = []
    for window in WINDOWS:
        units += measure_units(window, load_chunks(settings, window), counters, reference="qwen3")

    char_ratios = [u.ratio_to_reference for u in units if u.unit == "chars"]
    typical = next(u.ratio_to_reference.mean for u in units if u.unit == "chars" and u.window_chars == SPARSE_CHUNK_CHARS)
    safest = min(r.min for r in char_ratios)
    checks = []
    for target in TARGETS:
        for rule, ratio in (("mean_ratio", typical), ("min_ratio", safest)):
            limit = int(target * ratio)
            checks.append(check_char_limit(
                target, rule, limit, load_chunks(settings, limit), counters["qwen3"], counters["e5"], RUNNER_UP_CAP,
            ))
    return units, checks


async def compare_sparse(settings: Settings) -> list[SparseRun]:
    """후보 토크나이저마다 BM25 sparse 단독 검색을 잰다."""
    chunks = load_chunks(settings, SPARSE_CHUNK_CHARS)
    gold = load_gold(settings)
    benchmark = TokenizerBenchmark(QdrantChunkRepository(AsyncQdrantClient(url=settings.qdrant_url, prefer_grpc=True, timeout=60)))
    runs: list[SparseRun] = []
    for tokenizer in SPARSE_CANDIDATES + [TextTokenizer(name) for name in ANALYZER_CANDIDATES]:
        runs += await benchmark.run_sparse(SparseEncoder(tokenizer), chunks, gold)
    return runs


def write(settings: Settings, units: list[UnitLength], checks: list[CharLimitCheck], runs: list[SparseRun]) -> None:
    """길이 측정, sparse 요약, 문항별 판정, 1위 대비 짝지은 차이를 나눠 쓴다. 같은 결과면 같은 파일이 나온다."""
    out = settings.research_dir / OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)
    lengths = {"units": [u.model_dump() for u in units], "char_limit_checks": [c.model_dump() for c in checks]}
    (out / "length_units.json").write_text(json.dumps(lengths, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = [r.model_dump(exclude={"per_question"}) for r in runs]
    (out / "sparse_results.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    per_question = [{"tokenizer": r.tokenizer, "language": r.language, **s.model_dump()} for r in runs for s in r.per_question]
    (out / "sparse_per_question.jsonl").write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in per_question), encoding="utf-8")

    comparison = []
    for language in sorted({r.language for r in runs}):
        group = [r for r in runs if r.language == language]
        best = max(group, key=lambda r: (r.hit_at_5.mean, r.mrr_at_10.mean))
        for r in group:
            if r is best:
                continue
            comparison.append({
                "language": language, "best": best.tokenizer, "tokenizer": r.tokenizer,
                **{k: v.model_dump() for k, v in paired_against(best.per_question, r.per_question).items()},
            })
    (out / "sparse_comparison.json").write_text(json.dumps(comparison, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    logger.info("tokenizer_results_written", path=str(out), units=len(units), sparse_runs=len(runs))


def main(argv: list[str] | None = None) -> int:
    """길이 단위 측정과 sparse 비교를 함께 돌린다. 결과 파일은 매번 전부 덮어쓴다."""
    argparse.ArgumentParser(prog="tokenizer-selection").parse_args(argv)
    settings = get_settings()
    units, checks = measure_lengths(settings)
    runs = asyncio.run(compare_sparse(settings))
    write(settings, units, checks, runs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
