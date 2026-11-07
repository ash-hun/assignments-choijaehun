"""데이터베이스 선정 실험. 후보 DB마다 같은 청크와 벡터를 넣고 기능 통과 여부, 적재 시간, 질의 지연, ANN 재현율을 잰다."""
import time
import asyncio
import statistics
import numpy as np
from pydantic import BaseModel
from collections.abc import Awaitable, Callable

from app.repository.pgvector_chunk_repository import PgvectorChunkRepository
from app.repository.chroma_chunk_repository import ChromaChunkRepository
from app.repository.qdrant_chunk_repository import QdrantChunkRepository
from app.schema.vector_schema import SparseTerms, IndexContract
from app.service.eval.vector_projector import exact_top_k
from app.schema.chunk_schema import Chunk
from app.common.logger import get_logger

ChunkRepository = QdrantChunkRepository | PgvectorChunkRepository | ChromaChunkRepository
TOP_K = 10
LATENCY_REPEATS = 3
WARMUP_QUERIES = 5
BENCH_CONTRACT = IndexContract(embedding_model="bench", tokenizer="bench-hash", chunk_config_hash="fixed-1000")

logger = get_logger(__name__)


class FeatureResult(BaseModel):
    """기능 검사 하나의 결과. 실패하면 오류 요약을 남긴다."""

    passed: bool
    detail: str


class DatabaseRun(BaseModel):
    """후보 DB 하나, 차원 하나의 측정 결과."""

    database: str
    dim: int
    chunks: int
    features: dict[str, FeatureResult]
    load_seconds: float
    reload_seconds: float
    latency_ms_p50: float
    latency_ms_p95: float
    queries_timed: int
    ann_recall_at_10: float


class DatabaseBenchmark:
    """저장소 구현을 주입받아 같은 절차로 잰다. 컬렉션은 실행마다 지우고 새로 만든다."""

    def __init__(self, repositories: dict[str, ChunkRepository]) -> None:
        self._repositories = repositories

    async def run(
        self, chunks: list[Chunk], corpus: np.ndarray, queries: np.ndarray, sparse_chunks: list[SparseTerms], sparse_queries: list[SparseTerms],
    ) -> list[DatabaseRun]:
        """후보 순서대로 측정한다. 같은 머신에서 동시에 돌리면 서로의 지연에 섞이므로 하나씩 돈다."""
        runs = []
        for name, repo in self._repositories.items():
            logger.info("db_bench_start", database=name, dim=corpus.shape[1])
            runs.append(await self._run_one(name, repo, chunks, corpus, queries, sparse_chunks, sparse_queries))
        return runs

    async def _run_one(
        self, name: str, repo: ChunkRepository, chunks: list[Chunk], corpus: np.ndarray, queries: np.ndarray,
        sparse_chunks: list[SparseTerms], sparse_queries: list[SparseTerms],
    ) -> DatabaseRun:
        dim = corpus.shape[1]
        collection = f"bench_{dim}"
        ids = [c.chunk_id for c in chunks]
        features: dict[str, FeatureResult] = {}

        await repo.drop_collection(collection)
        await repo.ensure_collection(collection, dim, BENCH_CONTRACT)
        started = time.perf_counter()
        await repo.upsert(collection, chunks, corpus, sparse_chunks)
        load_seconds = time.perf_counter() - started
        started = time.perf_counter()
        await repo.upsert(collection, chunks, corpus, sparse_chunks)
        reload_seconds = time.perf_counter() - started

        async def check_upsert() -> str:
            stored = await repo.count(collection)
            assert stored == len(chunks), f"count {stored} != {len(chunks)} after upserting twice"
            return f"count stays {stored} after upserting twice"

        async def check_contract() -> str:
            contract = await repo.read_contract(collection)
            assert contract == BENCH_CONTRACT, f"read back {contract}"
            return "contract round-trips"

        async def check_filter() -> str:
            target = chunks[0].doc_id
            hits = await repo.search_dense(collection, queries[0], TOP_K, doc_id=target)
            docs = {chunks[ids.index(h)].doc_id for h in hits}
            assert hits and docs == {target}, f"filter returned docs {docs}"
            return f"{len(hits)} hits, all from {target}"

        async def check_sparse() -> str:
            hits = await repo.search_sparse(collection, sparse_chunks[0], TOP_K)
            assert hits and hits[0] == ids[0], f"self-query top hit {hits[:1]} != {ids[0]}"
            return "client-side sparse vector self-query returns itself first"

        async def check_hybrid() -> str:
            hits = await repo.search_hybrid(collection, queries[0], sparse_queries[0], TOP_K)
            assert len(hits) == TOP_K, f"{len(hits)} hits"
            return f"server-side fusion returned {len(hits)} hits"

        async def check_exact() -> str:
            expected = [[ids[i] for i in row] for row in exact_top_k(corpus, queries[:5], TOP_K)]
            got = [await repo.search_dense(collection, q, TOP_K, exact=True) for q in queries[:5]]
            assert got == expected, "exact search order differs from brute force"
            return "matches numpy brute force on 5 queries"

        checks: dict[str, Callable[[], Awaitable[str]]] = {
            "natural_key_upsert": check_upsert,
            "collection_metadata": check_contract,
            "metadata_filter": check_filter,
            "client_sparse_vectors": check_sparse,
            "hybrid_fusion": check_hybrid,
            "exact_search": check_exact,
        }
        for feature, check in checks.items():
            features[feature] = await _attempt(check)

        latencies: list[float] = []
        approx: list[list[str]] = []
        for q in queries[:WARMUP_QUERIES]:
            await repo.search_dense(collection, q, TOP_K)
        for _ in range(LATENCY_REPEATS):
            for q in queries:
                started = time.perf_counter()
                hits = await repo.search_dense(collection, q, TOP_K)
                latencies.append((time.perf_counter() - started) * 1000)
                if len(approx) < len(queries):
                    approx.append(hits)
        expected_all = [[ids[i] for i in row] for row in exact_top_k(corpus, queries, TOP_K)]
        recall = statistics.fmean(len(set(a) & set(e)) / TOP_K for a, e in zip(approx, expected_all))

        return DatabaseRun(
            database=name, dim=dim, chunks=len(chunks), features=features,
            load_seconds=round(load_seconds, 3), reload_seconds=round(reload_seconds, 3),
            latency_ms_p50=round(statistics.median(latencies), 2),
            latency_ms_p95=round(float(np.percentile(latencies, 95)), 2),
            queries_timed=len(latencies), ann_recall_at_10=round(recall, 4),
        )


async def _attempt(check: Callable[[], Awaitable[str]]) -> FeatureResult:
    try:
        return FeatureResult(passed=True, detail=await asyncio.wait_for(check(), timeout=60))
    except Exception as e:  # noqa: BLE001 - 기능 미지원은 어떤 예외로든 나타나므로 전부 기록한다.
        return FeatureResult(passed=False, detail=f"{type(e).__name__}: {str(e)[:200]}")
