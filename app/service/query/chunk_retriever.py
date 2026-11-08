"""질의 검색. 질문을 임베딩해 인덱스에서 dense 상위 k개 청크와 점수를 찾는다."""
import asyncio

from app.repository.qdrant_chunk_repository import QdrantChunkRepository
from app.client.embedding_client import EmbeddingClient
from app.schema.query_schema import RetrievedChunk


class ChunkRetriever:
    """임베딩은 CPU 연산이라 이벤트 루프를 막지 않게 스레드에서 돌린다."""

    def __init__(self, repository: QdrantChunkRepository, embedding: EmbeddingClient, collection: str) -> None:
        self._repository = repository
        self._embedding = embedding
        self._collection = collection

    async def retrieve(self, question: str, k: int) -> list[RetrievedChunk]:
        """점수 내림차순 상위 k개. 인덱스가 비어 있으면 빈 목록."""
        vectors = await asyncio.to_thread(self._embedding.embed_queries, [question])
        hits = await self._repository.search_dense_chunks(self._collection, vectors[0], k)
        return [RetrievedChunk(chunk=chunk, score=score) for chunk, score in hits]
