"""데이터베이스 선정 실험 진입점. 후보 DB 접속, 청크와 임시 벡터 준비, 측정, 결과 저장을 조립한다."""
import sys
import json
import time
import asyncio
import argparse
import chromadb
from psycopg import AsyncConnection
from qdrant_client import AsyncQdrantClient

from app.service.eval.database_benchmark import DatabaseRun, ChunkRepository, DatabaseBenchmark
from app.repository.pgvector_chunk_repository import PgvectorChunkRepository
from app.repository.chroma_chunk_repository import ChromaChunkRepository
from app.repository.qdrant_chunk_repository import QdrantChunkRepository
from app.service.ingest.chunk_splitter import FixedLengthSplitter
from app.service.ingest.document_loader import load_documents
from app.client.embedding_client import EmbeddingClient
from app.common.settings import Settings, get_settings
from app.service.eval.vector_projector import project
from app.schema.corpus_schema import CorpusManifest
from app.service.eval.term_hasher import hash_terms
from app.schema.gold_schema import GoldItem
from app.common.logger import get_logger

CHUNK_CHARS = 1000
# 384는 임시 모델의 원래 차원, 1024와 1536은 Embedding 후보들의 대표 차원이다.
DIMS = (384, 1024, 1536)
PROJECTION_SEED = 7
CONNECT_ATTEMPTS = 30
OUTPUT = "artifacts/database/results.json"

logger = get_logger(__name__)


async def connect(settings: Settings) -> dict[str, ChunkRepository]:
    """후보 DB가 막 떠서 아직 접속을 받지 못할 수 있어 몇 초 동안 다시 시도한다."""
    last_error: Exception | None = None
    for _ in range(CONNECT_ATTEMPTS):
        try:
            # REST로 연결하면 응답마다 약 45ms가 고정으로 끼어(research/database_selection.md) gRPC로 잰다.
            qdrant = AsyncQdrantClient(url=settings.qdrant_url, prefer_grpc=True, timeout=30)
            await qdrant.get_collections()
            pg = await AsyncConnection.connect(settings.postgres_dsn, autocommit=True)
            chroma = await chromadb.AsyncHttpClient(host=settings.chroma_host, port=settings.chroma_port)
            await chroma.heartbeat()
            return {
                "qdrant": QdrantChunkRepository(qdrant),
                "pgvector": PgvectorChunkRepository(pg),
                "chroma": ChromaChunkRepository(chroma),
            }
        except Exception as e:  # noqa: BLE001 - 기동 중인 DB는 여러 종류의 접속 오류를 낸다.
            last_error = e
            await asyncio.sleep(1)
    raise SystemExit(f"could not connect to candidate databases: {last_error}")


async def run(settings: Settings) -> list[DatabaseRun]:
    """같은 청크와 벡터를 차원별로 모든 후보에 넣고 잰다."""
    manifest_path = settings.data_dir / "corpus" / "manifests" / f"{settings.corpus_name}.json"
    manifest = CorpusManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    documents = load_documents(manifest, settings.data_dir / "corpus" / "raw" / settings.corpus_name)
    splitter = FixedLengthSplitter(CHUNK_CHARS)
    chunks = [c for d in documents for c in splitter.split(d)]
    lines = (settings.data_dir / "gold" / "dev_set.jsonl").read_text(encoding="utf-8").splitlines()
    questions = [GoldItem.model_validate_json(line).question for line in lines if line.strip()]

    started = time.perf_counter()
    embedder = EmbeddingClient(settings.bench_embedding_model, settings.model_cache_dir)
    corpus = embedder.embed_documents([c.text for c in chunks])
    queries = embedder.embed_queries(questions)
    logger.info("bench_embedded", chunks=len(chunks), queries=len(questions), seconds=round(time.perf_counter() - started, 1))
    sparse_chunks = [hash_terms(c.text) for c in chunks]
    sparse_queries = [hash_terms(q) for q in questions]

    benchmark = DatabaseBenchmark(await connect(settings))
    runs: list[DatabaseRun] = []
    for dim in DIMS:
        runs += await benchmark.run(
            chunks, project(corpus, dim, PROJECTION_SEED), project(queries, dim, PROJECTION_SEED), sparse_chunks, sparse_queries,
        )
    return runs


def main(argv: list[str] | None = None) -> int:
    """결과를 research/artifacts/database/results.json에 쓴다. 다시 실행하면 같은 파일을 덮어쓴다."""
    argparse.ArgumentParser(prog="database-selection").parse_args(argv)
    settings = get_settings()
    runs = asyncio.run(run(settings))
    out = settings.research_dir / OUTPUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps([r.model_dump() for r in runs], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    logger.info("db_bench_written", path=str(out), runs=len(runs), embedding_model=settings.bench_embedding_model, dims=list(DIMS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
