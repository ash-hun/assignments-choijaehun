"""Chroma에 청크와 dense, sparse 벡터를 저장하고 검색한다. 데이터베이스 선정 실험의 후보 구현이다."""
import numpy as np
from typing import Any
from chromadb.api import AsyncClientAPI
from chromadb.errors import InvalidArgumentError
from chromadb import Knn, Rrf, Schema, Search, SparseVector, VectorIndexConfig, SparseVectorIndexConfig

from app.schema.vector_schema import SparseTerms, IndexContract
from app.schema.chunk_schema import Chunk

SPARSE_KEY = "sparse"
UPSERT_BATCH = 128
CONTRACT_PREFIX = "contract_"


class ExactSearchUnsupported(RuntimeError):
    """Chroma는 HNSW를 거치지 않는 전수 비교 검색을 제공하지 않는다."""


class SparseSearchUnsupported(RuntimeError):
    """서버가 sparse 인덱스를 거부한 컬렉션에서 sparse, 하이브리드 검색을 부르면 난다."""


class ChromaChunkRepository:
    """컬렉션 하나가 인덱스 하나다. 인덱스 계약은 컬렉션 metadata에 접두어를 붙여 둔다."""

    def __init__(self, client: AsyncClientAPI) -> None:
        self._client = client
        self._sparse_disabled: dict[str, str] = {}

    async def ensure_collection(self, name: str, dim: int, contract: IndexContract) -> None:
        """없으면 cosine 공간과 sparse 인덱스로 만든다. 서버가 sparse 인덱스를 거부하면 dense만으로 만들고 그 사유를 남긴다."""
        metadata: dict[str, Any] = {f"{CONTRACT_PREFIX}{k}": v for k, v in contract.model_dump().items()}
        try:
            await self._client.get_or_create_collection(name, metadata=metadata, schema=_schema(sparse=True), embedding_function=None)
        except InvalidArgumentError as e:
            # 오픈소스 로컬 서버는 "Sparse vector indexing is not enabled in local"로 거부한다(Chroma Cloud 전용 기능).
            if "sparse" not in str(e).lower():
                raise
            self._sparse_disabled[name] = str(e)
            await self._client.get_or_create_collection(name, metadata=metadata, schema=_schema(sparse=False), embedding_function=None)

    async def drop_collection(self, name: str) -> None:
        """실험용 초기화. 운영 경로에서는 부르지 않는다."""
        names = {c.name for c in await self._client.list_collections()}
        if name in names:
            await self._client.delete_collection(name)

    async def read_contract(self, name: str) -> IndexContract | None:
        """컬렉션 metadata에서 계약 필드만 골라 읽는다."""
        collection = await self._client.get_collection(name, embedding_function=None)
        metadata = collection.metadata or {}
        fields = {k[len(CONTRACT_PREFIX):]: v for k, v in metadata.items() if k.startswith(CONTRACT_PREFIX)}
        return IndexContract.model_validate(fields) if fields else None

    async def upsert(self, name: str, chunks: list[Chunk], dense: np.ndarray, sparse: list[SparseTerms]) -> None:
        """chunk_id를 Chroma id로 덮어쓴다. sparse 벡터는 metadata 필드로 넣는다."""
        collection = await self._client.get_collection(name, embedding_function=None)
        for start in range(0, len(chunks), UPSERT_BATCH):
            batch = chunks[start:start + UPSERT_BATCH]
            await collection.upsert(
                ids=[c.chunk_id for c in batch],
                embeddings=[dense[start + i] for i in range(len(batch))],
                documents=[c.text for c in batch],
                metadatas=[self._metadata(name, c, sparse[start + i]) for i, c in enumerate(batch)],
            )

    def _metadata(self, name: str, chunk: Chunk, sparse: SparseTerms) -> dict[str, Any]:
        metadata: dict[str, Any] = {"doc_id": chunk.doc_id, "ordinal": chunk.ordinal}
        if name not in self._sparse_disabled:
            metadata[SPARSE_KEY] = SparseVector(indices=sparse.indices, values=sparse.values)
        return metadata

    def _require_sparse(self, name: str) -> None:
        if name in self._sparse_disabled:
            raise SparseSearchUnsupported(self._sparse_disabled[name])

    async def count(self, name: str) -> int:
        """저장된 청크 수."""
        collection = await self._client.get_collection(name, embedding_function=None)
        return await collection.count()

    async def search_dense(self, name: str, vector: np.ndarray, k: int, exact: bool = False, doc_id: str | None = None) -> list[str]:
        """HNSW 코사인 상위 k개 chunk_id."""
        if exact:
            raise ExactSearchUnsupported("chroma has no exact (brute-force) query mode")
        collection = await self._client.get_collection(name, embedding_function=None)
        result = await collection.query(query_embeddings=[vector], n_results=k, where={"doc_id": doc_id} if doc_id else None, include=[])
        return list(result["ids"][0])

    async def search_sparse(self, name: str, sparse: SparseTerms, k: int) -> list[str]:
        """sparse 인덱스 상위 k개 chunk_id."""
        self._require_sparse(name)
        collection = await self._client.get_collection(name, embedding_function=None)
        query = SparseVector(indices=sparse.indices, values=sparse.values)
        result = await collection.search(Search().rank(Knn(query=query, key=SPARSE_KEY, limit=k)).limit(k))
        return list(result["ids"][0])

    async def search_hybrid(self, name: str, vector: np.ndarray, sparse: SparseTerms, k: int) -> list[str]:
        """dense와 sparse 순위를 서버에서 RRF로 합친다."""
        self._require_sparse(name)
        collection = await self._client.get_collection(name, embedding_function=None)
        ranks = Rrf([
            Knn(query=vector.tolist(), limit=k * 4, return_rank=True),
            Knn(query=SparseVector(indices=sparse.indices, values=sparse.values), key=SPARSE_KEY, limit=k * 4, return_rank=True),
        ])
        result = await collection.search(Search().rank(ranks).limit(k))
        return list(result["ids"][0])


def _schema(sparse: bool) -> Schema:
    """cosine dense 인덱스, 필요하면 sparse 인덱스. Chroma는 configuration과 schema를 함께 받지 않아 cosine도 schema에 둔다."""
    schema = Schema()
    schema.create_index(config=VectorIndexConfig(space="cosine"))
    if sparse:
        schema.create_index(config=SparseVectorIndexConfig(), key=SPARSE_KEY)
    return schema
