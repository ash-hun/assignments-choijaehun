"""Reproduce the benchmark path with the real repository and toggle one factor at a time."""
import time
import asyncio
import statistics
import numpy as np
from qdrant_client import AsyncQdrantClient

from app.repository.qdrant_chunk_repository import QdrantChunkRepository
from app.service.eval.database_benchmark import BENCH_CONTRACT
from app.service.eval.term_hasher import hash_terms
from app.schema.chunk_schema import Chunk


async def median_ms(fn, n: int = 30) -> float:
    for _ in range(3):
        await fn()
    samples = []
    for _ in range(n):
        t = time.perf_counter()
        await fn()
        samples.append((time.perf_counter() - t) * 1000)
    return round(statistics.median(samples), 2)


async def main() -> None:
    rng = np.random.default_rng(0)
    vecs = rng.standard_normal((587, 384)).astype(np.float32)
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    chunks = [Chunk(chunk_id=f"{i:032x}", doc_id=f"d{i % 50}.md", ordinal=0, text="word " * 200) for i in range(587)]
    sparse = [hash_terms(c.text + str(i)) for i, c in enumerate(chunks)]
    for label, client in [("rest timeout=30", AsyncQdrantClient(url="http://qdrant:6333", timeout=30)),
                          ("grpc", AsyncQdrantClient(host="qdrant", grpc_port=6334, prefer_grpc=True, timeout=30))]:
        repo = QdrantChunkRepository(client)
        await repo.drop_collection("probe2")
        await repo.ensure_collection("probe2", 384, BENCH_CONTRACT)
        await repo.upsert("probe2", chunks, vecs, sparse)
        q = vecs[1]
        print(label, "search_dense", await median_ms(lambda: repo.search_dense("probe2", q, 10)))
        print(label, "raw query_points no search_params", await median_ms(
            lambda: client.query_points("probe2", query=q.tolist(), using="dense", limit=10, with_payload=["chunk_id"])))
        await repo.drop_collection("probe2")


asyncio.run(main())
