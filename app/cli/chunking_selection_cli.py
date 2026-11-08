"""Chunking 선정 실험 진입점. 분할 방식 5종을 먼저 비교하고, 1위 방식만 크기와 겹침을 바꿔 최종 설정을 고른다."""
import sys
import json
import time
import asyncio
import argparse
from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient

from app.service.eval.chunking_benchmark import ChunkingRun, ChunkingVerdict, ChunkingBenchmark, pick_best
from app.repository.qdrant_chunk_repository import QdrantChunkRepository
from app.service.ingest.chunk_splitter import ChunkMethod, ChunkSplitter
from app.cli.embedding_selection_cli import CANDIDATES, load_gold
from app.service.ingest.sentence_embedder import SentenceEmbedder
from app.service.ingest.document_loader import load_documents
from app.client.embedding_client import EmbeddingClient
from app.common.settings import Settings, get_settings
from app.schema.corpus_schema import CorpusManifest
from app.schema.chunk_schema import Document
from app.common.logger import get_logger

OUTPUT_DIR = "artifacts/chunking"
EMBEDDING = "Qwen/Qwen3-Embedding-0.6B"
# 단순한 순서. 판정이 끝까지 같으면 앞쪽을 고른다.
METHODS: tuple[ChunkMethod, ...] = ("fixed", "sliding", "recursive", "structure", "semantic")
FIRST_SIZE = 512
SIZES = (256, 512, 1024)
# sliding은 겹침이 방식의 정의라(창을 절반씩 민다) 겹침 후보가 다르다. 0%나 15%로 두면 fixed와 같아진다.
OVERLAP_RATIOS: dict[ChunkMethod, tuple[float, ...]] = {"sliding": (0.25, 0.5)}
DEFAULT_OVERLAP_RATIOS = (0.0, 0.15)
FIRST_OVERLAP_RATIO: dict[ChunkMethod, float] = {"sliding": 0.5}
DEFAULT_FIRST_OVERLAP_RATIO = 0.15

logger = get_logger(__name__)


class ChunkingMethod(BaseModel):
    """1단계 판정 규칙이 고른 방식과 2단계에 실제로 쓴 방식. 둘이 다르면 사람이 규칙을 넘어선 것이다."""

    rule_choice: ChunkMethod
    used: ChunkMethod


def load_corpus(settings: Settings) -> list[Document]:
    """manifest에 고정된 Corpus를 정제해 읽는다."""
    manifest_path = settings.data_dir / "corpus" / "manifests" / f"{settings.corpus_name}.json"
    manifest = CorpusManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    return load_documents(manifest, settings.data_dir / "corpus" / "raw" / settings.corpus_name)


def make_splitter(client: EmbeddingClient, embedder: SentenceEmbedder, method: ChunkMethod, size: int, ratio: float) -> ChunkSplitter:
    """겹침은 크기의 비율로 받아 토큰 수로 바꾼다."""
    embed = embedder if method == "semantic" else None
    return ChunkSplitter(method, size, round(size * ratio), client.token_count, client.token_offsets, embed)


async def run(settings: Settings, method_override: ChunkMethod | None) -> tuple[list[ChunkingRun], ChunkingVerdict, ChunkingMethod, ChunkingVerdict]:
    """방식 비교와 크기, 겹침 비교를 이어서 돌린다. 이미 잰 설정은 다시 재지 않는다.

    method_override가 있으면 1단계 규칙의 선택 대신 그 방식으로 2단계를 돈다. 규칙의 선택과 실제 방식을 함께 남긴다.
    """
    documents = load_corpus(settings)
    gold = load_gold(settings)
    candidate = next(c for c in CANDIDATES if c.name == EMBEDDING)
    client = EmbeddingClient(candidate.name, settings.model_cache_dir, candidate.query_prefix, candidate.document_prefix)
    benchmark = ChunkingBenchmark(QdrantChunkRepository(AsyncQdrantClient(url=settings.qdrant_url, prefer_grpc=True, timeout=60)), client)
    embedder = SentenceEmbedder(client)
    measured: dict[str, list[ChunkingRun]] = {}

    async def measure(splitter: ChunkSplitter) -> list[ChunkingRun]:
        if splitter.name not in measured:
            started = time.perf_counter()
            chunks = [c for d in documents for c in splitter.split(d)]
            split_seconds = time.perf_counter() - started
            logger.info("chunking_config_start", config=splitter.name, chunks=len(chunks), split_seconds=round(split_seconds, 1))
            measured[splitter.name] = await benchmark.run(splitter.name, chunks, gold, split_seconds)
        return measured[splitter.name]

    first_size = min(FIRST_SIZE, candidate.max_tokens)
    first = {m: make_splitter(client, embedder, m, first_size, FIRST_OVERLAP_RATIO.get(m, DEFAULT_FIRST_OVERLAP_RATIO)) for m in METHODS}
    method_runs = []
    for splitter in first.values():
        method_runs += await measure(splitter)
    by_method = pick_best(method_runs)
    rule_method = next(m for m, s in first.items() if s.name == by_method.chosen)
    method = method_override or rule_method
    chosen_method = ChunkingMethod(rule_choice=rule_method, used=method)

    size_runs = []
    for size in (s for s in SIZES if s <= candidate.max_tokens):
        for ratio in OVERLAP_RATIOS.get(method, DEFAULT_OVERLAP_RATIOS):
            size_runs += await measure(make_splitter(client, embedder, method, size, ratio))
    by_size = pick_best(size_runs)
    return [r for runs in measured.values() for r in runs], by_method, chosen_method, by_size


def write(settings: Settings, runs: list[ChunkingRun], by_method: ChunkingVerdict, method: ChunkingMethod, by_size: ChunkingVerdict) -> None:
    """요약, 문항별 판정, 두 단계 판정을 나눠 쓴다. 같은 결과면 시간 값을 빼고 같은 파일이 나온다."""
    out = settings.research_dir / OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)
    summary = [r.model_dump(exclude={"per_question"}) for r in runs]
    (out / "results.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    per_question = [{"config": r.config, "language": r.language, **s.model_dump()} for r in runs for s in r.per_question]
    (out / "per_question.jsonl").write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in per_question), encoding="utf-8")
    verdicts = {"by_method": by_method.model_dump(), "method": method.model_dump(), "by_size_and_overlap": by_size.model_dump()}
    (out / "verdict.json").write_text(json.dumps(verdicts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    logger.info("chunking_results_written", path=str(out), configs=len({r.config for r in runs}), chosen=by_size.chosen)


def main(argv: list[str] | None = None) -> int:
    """두 단계를 함께 돌린다. 결과 파일은 매번 전부 덮어쓴다."""
    parser = argparse.ArgumentParser(prog="chunking-selection")
    parser.add_argument("--method", choices=METHODS, help="1단계 규칙의 선택 대신 2단계에 쓸 방식. 근거는 research/chunking_selection.md에 기록")
    args = parser.parse_args(argv)
    settings = get_settings()
    runs, by_method, method, by_size = asyncio.run(run(settings, args.method))
    write(settings, runs, by_method, method, by_size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
