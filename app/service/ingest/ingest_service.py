"""Ingest 파이프라인 조립. 문서를 청크로 나눠 dense, sparse 벡터와 함께 저장하고 컬렉션에 인덱스 계약을 기록한다."""
import time
from pydantic import BaseModel

from app.repository.qdrant_chunk_repository import QdrantChunkRepository
from app.service.ingest.sparse_encoder import SparseEncoder
from app.service.ingest.chunk_splitter import ChunkSplitter
from app.client.embedding_client import EmbeddingClient
from app.schema.chunk_schema import Chunk, Document
from app.schema.vector_schema import IndexContract
from app.common.logger import get_logger

logger = get_logger(__name__)


class IngestResult(BaseModel):
    """한 번 실행한 결과. removed는 원문에서 사라져 지운 청크 수다."""

    collection: str
    documents: int
    chunks: int
    removed: int
    seconds: float


class IngestService:
    """같은 원문과 설정이면 같은 컬렉션, 같은 포인트로 수렴한다. 중간에 죽으면 다시 실행하면 된다."""

    def __init__(
        self, repository: QdrantChunkRepository, embedding: EmbeddingClient, splitter: ChunkSplitter,
        sparse: SparseEncoder, contract: IndexContract, corpus: str,
    ) -> None:
        self._repository = repository
        self._embedding = embedding
        self._splitter = splitter
        self._sparse = sparse
        self._contract = contract
        self._corpus = corpus

    @property
    def collection(self) -> str:
        """이 설정이 쓰는 컬렉션 이름."""
        return self._contract.collection_name(self._corpus)

    async def run(self, documents: list[Document], urls: dict[str, str]) -> IngestResult:
        """분할, 임베딩, 저장, 사라진 청크 정리 순서. 컬렉션이 이미 있으면 그대로 두고 upsert한다."""
        started = time.perf_counter()
        chunks = [
            chunk.model_copy(update={"title": document.title, "url": urls.get(document.doc_id, "")})
            for document in documents for chunk in self._splitter.split(document)
        ]
        chunks = _unique(chunks)
        logger.info("ingest_split", documents=len(documents), chunks=len(chunks), config=self._splitter.name)
        dense = self._embedding.embed_documents([c.text for c in chunks])
        # BM25 문서 가중치는 Corpus 전체 평균 길이로 정규화하므로 한 번에 넣는다.
        sparse = self._sparse.encode_documents([c.text for c in chunks])
        await self._repository.ensure_collection(self.collection, int(dense.shape[1]), self._contract)
        await self._repository.upsert(self.collection, chunks, dense, sparse)
        removed = await self._repository.delete_except(self.collection, {c.chunk_id for c in chunks})
        result = IngestResult(collection=self.collection, documents=len(documents), chunks=len(chunks), removed=removed,
                              seconds=round(time.perf_counter() - started, 1))
        logger.info("ingest_done", **result.model_dump())
        return result


def _unique(chunks: list[Chunk]) -> list[Chunk]:
    # 같은 문서 안에 같은 내용의 청크가 두 번 나오면 chunk_id가 같아 한 포인트가 된다. 개수를 저장 상태와 맞춘다.
    return list({c.chunk_id: c for c in chunks}.values())
