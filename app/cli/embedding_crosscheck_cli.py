"""Embedding 교차 확인 실험 진입점. 확정한 Chunking 청크로 Qwen3와 e5를 다시 색인해 재고 판정을 저장한다."""
import sys
import json
import time
import asyncio
from qdrant_client import AsyncQdrantClient

from app.service.eval.embedding_crosscheck import ModelResult, CrosscheckVerdict, judge, truncated_chunks
from app.repository.qdrant_chunk_repository import QdrantChunkRepository
from app.service.ingest.chunk_splitter import ChunkMethod, ChunkSplitter
from app.service.eval.chunking_benchmark import ChunkingBenchmark
from app.cli.embedding_selection_cli import CANDIDATES, load_gold
from app.client.embedding_client import EmbeddingClient
from app.cli.chunking_selection_cli import load_corpus
from app.common.settings import Settings, get_settings
from app.schema.gold_schema import GoldItem
from app.schema.chunk_schema import Chunk
from app.common.logger import get_logger

OUTPUT_DIR = "artifacts/embedding_crosscheck"
INCUMBENT = "Qwen/Qwen3-Embedding-0.6B"
CHALLENGER = "intfloat/multilingual-e5-large"
# Chunking 선정 결정(research/chunking_selection.md). 길이는 기존 선택인 Qwen3 토큰으로 잰다.
CHUNK_METHOD: ChunkMethod = "structure"
CHUNK_SIZE = 512
CHUNK_OVERLAP = 77

logger = get_logger(__name__)


def make_client(settings: Settings, name: str) -> tuple[EmbeddingClient, int]:
    """후보 정의의 접두어로 클라이언트를 만들고 모델 최대 입력을 함께 돌려준다."""
    candidate = next(c for c in CANDIDATES if c.name == name)
    client = EmbeddingClient(candidate.name, settings.model_cache_dir, candidate.query_prefix, candidate.document_prefix)
    return client, candidate.max_tokens


async def measure(
    repository: QdrantChunkRepository, client: EmbeddingClient, max_input: int, config: str,
    chunks: list[Chunk], gold: dict[str, list[GoldItem]], split_seconds: float,
) -> ModelResult:
    """모델 하나로 색인하고 언어별로 잰다. 컬렉션은 ChunkingBenchmark가 시작과 끝에 지운다."""
    truncated = truncated_chunks(client, chunks, max_input)
    logger.info("crosscheck_model_start", model=client.model_name, chunks=len(chunks), truncated=truncated)
    runs = await ChunkingBenchmark(repository, client).run(config, chunks, gold, split_seconds)
    return ModelResult(model=client.model_name, max_input_tokens=max_input, truncated_chunks=truncated, runs=runs)


async def run(settings: Settings) -> tuple[ModelResult, ModelResult]:
    """두 모델에 같은 청크를 넣는다. 모델은 하나씩 올려 메모리와 CPU를 나눠 쓰지 않게 한다."""
    documents = load_corpus(settings)
    gold = load_gold(settings)
    repository = QdrantChunkRepository(AsyncQdrantClient(url=settings.qdrant_url, prefer_grpc=True, timeout=60))

    client, max_input = make_client(settings, INCUMBENT)
    splitter = ChunkSplitter(CHUNK_METHOD, CHUNK_SIZE, CHUNK_OVERLAP, client.token_count, client.token_offsets)
    started = time.perf_counter()
    chunks = [c for d in documents for c in splitter.split(d)]
    split_seconds = time.perf_counter() - started
    incumbent = await measure(repository, client, max_input, splitter.name, chunks, gold, split_seconds)

    del client
    client, max_input = make_client(settings, CHALLENGER)
    challenger = await measure(repository, client, max_input, splitter.name, chunks, gold, split_seconds)
    return incumbent, challenger


def write(settings: Settings, incumbent: ModelResult, challenger: ModelResult, verdict: CrosscheckVerdict) -> None:
    """요약, 문항별 판정, 판정을 나눠 쓴다. 같은 결과면 시간 값을 빼고 같은 파일이 나온다."""
    out = settings.research_dir / OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)
    results = [
        {"model": m.model, "max_input_tokens": m.max_input_tokens, "truncated_chunks": m.truncated_chunks,
         **r.model_dump(exclude={"per_question"})}
        for m in (incumbent, challenger) for r in m.runs
    ]
    (out / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    per_question = [
        {"model": m.model, "language": r.language, **s.model_dump()}
        for m in (incumbent, challenger) for r in m.runs for s in r.per_question
    ]
    (out / "per_question.jsonl").write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in per_question), encoding="utf-8")
    (out / "verdict.json").write_text(json.dumps(verdict.model_dump(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    logger.info("crosscheck_results_written", path=str(out), chosen=verdict.chosen, reason=verdict.reason)


def main() -> int:
    """두 모델을 재고 판정한다. 결과 파일은 매번 전부 덮어쓴다."""
    settings = get_settings()
    incumbent, challenger = asyncio.run(run(settings))
    write(settings, incumbent, challenger, judge(incumbent, challenger))
    return 0


if __name__ == "__main__":
    sys.exit(main())
