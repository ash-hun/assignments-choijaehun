"""Embedding 선정 실험 진입점. 후보 모델 정의, 청크와 dev set 준비, 측정, 결과 저장을 조립한다."""
import sys
import json
import asyncio
import argparse
from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient

from app.service.eval.embedding_benchmark import EmbeddingRun, EmbeddingBenchmark
from app.repository.qdrant_chunk_repository import QdrantChunkRepository
from app.service.ingest.chunk_splitter import FixedLengthSplitter
from app.service.ingest.document_loader import load_documents
from app.service.eval.retrieval_metric import paired_against
from app.client.embedding_client import EmbeddingClient
from app.common.settings import Settings, get_settings
from app.schema.corpus_schema import CorpusManifest
from app.schema.gold_schema import GoldItem
from app.common.logger import get_logger

CHUNK_CHARS = 1000
OUTPUT_DIR = "artifacts/embedding"
BGE_QUERY = "Represent this sentence for searching relevant passages: "
QWEN_QUERY = (
    "Instruct: Given a question about the uv Python package manager, "
    "retrieve documentation passages that answer the question\nQuery: "
)

logger = get_logger(__name__)


class EmbeddingCandidate(BaseModel):
    """후보 모델과 모델 카드가 요구하는 접두어, 최대 입력 토큰."""

    name: str
    max_tokens: int
    query_prefix: str = ""
    document_prefix: str = ""


CANDIDATES = [
    EmbeddingCandidate(name="BAAI/bge-small-en-v1.5", max_tokens=512, query_prefix=BGE_QUERY),
    EmbeddingCandidate(name="BAAI/bge-base-en-v1.5", max_tokens=512, query_prefix=BGE_QUERY),
    EmbeddingCandidate(name="snowflake/snowflake-arctic-embed-m", max_tokens=512, query_prefix=BGE_QUERY),
    EmbeddingCandidate(name="nomic-ai/nomic-embed-text-v1.5", max_tokens=8192, query_prefix="search_query: ", document_prefix="search_document: "),
    EmbeddingCandidate(name="intfloat/multilingual-e5-large", max_tokens=512, query_prefix="query: ", document_prefix="passage: "),
    EmbeddingCandidate(name="Qwen/Qwen3-Embedding-0.6B", max_tokens=32768, query_prefix=QWEN_QUERY),
]


def load_gold(settings: Settings) -> dict[str, list[GoldItem]]:
    """영어 정본과 한국어 번역 묶음."""
    gold_dir = settings.data_dir / "gold"
    result = {}
    for language, name in (("en", "dev_set.jsonl"), ("ko", "dev_set_ko.jsonl")):
        lines = (gold_dir / name).read_text(encoding="utf-8").splitlines()
        result[language] = [GoldItem.model_validate_json(line) for line in lines if line.strip()]
    return result


async def run(settings: Settings, names: list[str] | None) -> list[EmbeddingRun]:
    """후보를 하나씩 색인하고 잰다. 모델을 동시에 올리면 메모리와 CPU를 나눠 써서 시간 측정이 흔들린다."""
    manifest_path = settings.data_dir / "corpus" / "manifests" / f"{settings.corpus_name}.json"
    manifest = CorpusManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    documents = load_documents(manifest, settings.data_dir / "corpus" / "raw" / settings.corpus_name)
    splitter = FixedLengthSplitter(CHUNK_CHARS)
    chunks = [c for d in documents for c in splitter.split(d)]
    gold = load_gold(settings)
    benchmark = EmbeddingBenchmark(QdrantChunkRepository(AsyncQdrantClient(url=settings.qdrant_url, prefer_grpc=True, timeout=60)))

    runs: list[EmbeddingRun] = []
    for candidate in CANDIDATES:
        if names and candidate.name not in names:
            continue
        logger.info("embedding_candidate_start", model=candidate.name)
        client = EmbeddingClient(candidate.name, settings.model_cache_dir, candidate.query_prefix, candidate.document_prefix)
        runs += await benchmark.run(client, candidate.max_tokens, chunks, gold)
    return runs


def write(settings: Settings, runs: list[EmbeddingRun]) -> None:
    """요약, 문항별 판정, 최고 모델 대비 paired 차이를 나눠 쓴다. 같은 결과면 같은 파일이 나온다."""
    out = settings.research_dir / OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)
    summary = [r.model_dump(exclude={"per_question"}) for r in runs]
    (out / "results.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    per_question = [
        {"model": r.model, "language": r.language, **s.model_dump()} for r in runs for s in r.per_question
    ]
    (out / "per_question.jsonl").write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in per_question), encoding="utf-8")

    comparison = []
    for language in sorted({r.language for r in runs}):
        group = [r for r in runs if r.language == language]
        best = max(group, key=lambda r: (r.hit_at_5.mean, r.mrr_at_10.mean))
        for r in group:
            if r is best:
                continue
            comparison.append({
                "language": language, "best": best.model, "model": r.model,
                **{k: v.model_dump() for k, v in paired_against(best.per_question, r.per_question).items()},
            })
    (out / "comparison.json").write_text(json.dumps(comparison, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    logger.info("embedding_results_written", path=str(out), runs=len(runs))


def main(argv: list[str] | None = None) -> int:
    """--model로 일부 후보만 돌릴 수 있다. 결과 파일은 돌린 후보만으로 덮어쓴다."""
    parser = argparse.ArgumentParser(prog="embedding-selection")
    parser.add_argument("--model", action="append", help="후보 모델 이름. 생략하면 전부")
    args = parser.parse_args(argv)
    settings = get_settings()
    write(settings, asyncio.run(run(settings, args.model)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
