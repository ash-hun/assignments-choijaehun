"""질의 검색. 설정한 방식(dense, BM25, RRF, CC)으로 상위 k개 청크를 고르고, 거절 판정용 dense 최고 점수를 함께 낸다."""
import asyncio
from dataclasses import dataclass

from app.service.query.score_fusion import convex_combination, reciprocal_rank_fusion
from app.schema.query_schema import Retrieval, RetrievalMode, RetrievedChunk
from app.repository.qdrant_chunk_repository import QdrantChunkRepository
from app.service.ingest.sparse_encoder import SparseEncoder
from app.client.embedding_client import EmbeddingClient
from app.schema.chunk_schema import Chunk


@dataclass(frozen=True)
class FusionSettings:
    """융합 후보 수(pool)는 dense와 BM25에서 각각 가져오는 개수다. 두 Hybrid가 같은 후보를 쓰게 고정한다."""

    mode: RetrievalMode = "dense"
    pool: int = 40
    rrf_k: int = 60
    cc_alpha: float = 0.5


class ChunkRetriever:
    """임베딩은 CPU 연산이라 이벤트 루프를 막지 않게 스레드에서 돌린다. dense가 아닌 방식은 sparse 인코더가 필요하다."""

    def __init__(
        self, repository: QdrantChunkRepository, embedding: EmbeddingClient, collection: str,
        encoder: SparseEncoder | None = None, fusion: FusionSettings = FusionSettings(),
    ) -> None:
        if fusion.mode != "dense" and encoder is None:
            raise ValueError(f"retrieval mode {fusion.mode} needs a sparse encoder")
        self._repository = repository
        self._embedding = embedding
        self._collection = collection
        self._encoder = encoder
        self._fusion = fusion

    @property
    def mode(self) -> RetrievalMode:
        """검색 방식."""
        return self._fusion.mode

    async def retrieve(self, question: str, k: int) -> Retrieval:
        """검색 방식 점수 내림차순 상위 k개. 인덱스가 비어 있으면 빈 목록과 None."""
        vectors = await asyncio.to_thread(self._embedding.embed_queries, [question])
        if self._fusion.mode == "dense":
            dense = await self._repository.search_dense_chunks(self._collection, vectors[0], k)
            return Retrieval(hits=[RetrievedChunk(chunk=c, score=s) for c, s in dense],
                             top_dense_score=dense[0][1] if dense else None)
        if self._encoder is None:
            raise ValueError(f"retrieval mode {self._fusion.mode} needs a sparse encoder")
        # 거절 판정은 dense 점수로 한다. BM25 단독도 같은 판정을 쓰도록 dense를 함께 조회한다.
        depth = k if self._fusion.mode == "bm25" else max(self._fusion.pool, k)
        dense, sparse = await asyncio.gather(
            self._repository.search_dense_chunks(self._collection, vectors[0], depth),
            self._repository.search_sparse_chunks(self._collection, self._encoder.encode_query(question), depth),
        )
        chunks: dict[str, Chunk] = {c.chunk_id: c for c, _ in dense + sparse}
        ranked = self._rank([(c.chunk_id, s) for c, s in dense], [(c.chunk_id, s) for c, s in sparse])
        return Retrieval(hits=[RetrievedChunk(chunk=chunks[cid], score=s) for cid, s in ranked[:k]],
                         top_dense_score=dense[0][1] if dense else None)

    def _rank(self, dense: list[tuple[str, float]], sparse: list[tuple[str, float]]) -> list[tuple[str, float]]:
        if self._fusion.mode == "bm25":
            return sorted(sparse, key=lambda item: (-item[1], item[0]))
        if self._fusion.mode == "rrf":
            return reciprocal_rank_fusion([cid for cid, _ in dense], [cid for cid, _ in sparse], self._fusion.rrf_k)
        return convex_combination(dense, sparse, self._fusion.cc_alpha)
