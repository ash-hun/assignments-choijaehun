"""Qdrant에 청크와 dense, sparse 벡터를 저장하고 검색한다. 데이터베이스 선정 실험의 후보 구현이다."""
import uuid
import numpy as np
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qm

from app.schema.vector_schema import SparseTerms, IndexContract
from app.schema.chunk_schema import Chunk

DENSE = "dense"
SPARSE = "sparse"
UPSERT_BATCH = 128
# 청크 id(sha256 앞 32자)를 Qdrant 포인트 id(UUID)로 옮긴다. 같은 청크면 같은 포인트라 upsert가 수렴한다.
POINT_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "elice-rag-qa/qdrant-point")


class QdrantChunkRepository:
    """컬렉션 하나가 인덱스 하나다. 인덱스 계약은 컬렉션 metadata에 둔다."""

    def __init__(self, client: AsyncQdrantClient) -> None:
        self._client = client

    async def ensure_collection(self, name: str, dim: int, contract: IndexContract) -> None:
        """없으면 만든다. 있으면 그대로 둔다."""
        if await self._client.collection_exists(name):
            return
        await self._client.create_collection(
            collection_name=name,
            vectors_config={DENSE: qm.VectorParams(size=dim, distance=qm.Distance.COSINE)},
            sparse_vectors_config={SPARSE: qm.SparseVectorParams(modifier=qm.Modifier.IDF)},
            metadata=contract.model_dump(),
        )
        await self._client.create_payload_index(name, field_name="doc_id", field_schema=qm.PayloadSchemaType.KEYWORD)

    async def drop_collection(self, name: str) -> None:
        """실험용 초기화. 운영 경로에서는 부르지 않는다."""
        if await self._client.collection_exists(name):
            await self._client.delete_collection(name)

    async def read_contract(self, name: str) -> IndexContract | None:
        """컬렉션 metadata에서 인덱스 계약을 읽는다."""
        info = await self._client.get_collection(name)
        metadata = info.config.metadata
        return IndexContract.model_validate(metadata) if metadata else None

    async def upsert(self, name: str, chunks: list[Chunk], dense: np.ndarray, sparse: list[SparseTerms]) -> None:
        """chunk_id에서 계산한 포인트 id로 덮어쓴다."""
        for start in range(0, len(chunks), UPSERT_BATCH):
            points = [
                qm.PointStruct(
                    id=str(uuid.uuid5(POINT_NAMESPACE, chunk.chunk_id)),
                    vector={DENSE: dense[i].tolist(), SPARSE: qm.SparseVector(indices=sparse[i].indices, values=sparse[i].values)},
                    payload={"chunk_id": chunk.chunk_id, "doc_id": chunk.doc_id, "ordinal": chunk.ordinal, "text": chunk.text},
                )
                for i, chunk in enumerate(chunks[start:start + UPSERT_BATCH], start=start)
            ]
            await self._client.upsert(name, points=points, wait=True)

    async def count(self, name: str) -> int:
        """저장된 청크 수."""
        result = await self._client.count(name, exact=True)
        return result.count

    async def search_dense(self, name: str, vector: np.ndarray, k: int, exact: bool = False, doc_id: str | None = None) -> list[str]:
        """코사인 유사도 상위 k개 chunk_id. exact면 HNSW를 거치지 않고 전수 비교한다."""
        result = await self._client.query_points(
            name, query=vector.tolist(), using=DENSE, limit=k, with_payload=["chunk_id"],
            search_params=qm.SearchParams(exact=exact), query_filter=_doc_filter(doc_id),
        )
        return [str((p.payload or {})["chunk_id"]) for p in result.points]

    async def search_sparse(self, name: str, sparse: SparseTerms, k: int) -> list[str]:
        """sparse 내적(IDF 가중) 상위 k개 chunk_id."""
        result = await self._client.query_points(
            name, query=qm.SparseVector(indices=sparse.indices, values=sparse.values), using=SPARSE, limit=k, with_payload=["chunk_id"],
        )
        return [str((p.payload or {})["chunk_id"]) for p in result.points]

    async def search_hybrid(self, name: str, vector: np.ndarray, sparse: SparseTerms, k: int) -> list[str]:
        """dense와 sparse 후보를 서버에서 RRF로 합친 상위 k개 chunk_id."""
        result = await self._client.query_points(
            name,
            prefetch=[
                qm.Prefetch(query=vector.tolist(), using=DENSE, limit=k * 4),
                qm.Prefetch(query=qm.SparseVector(indices=sparse.indices, values=sparse.values), using=SPARSE, limit=k * 4),
            ],
            query=qm.FusionQuery(fusion=qm.Fusion.RRF),
            limit=k,
            with_payload=["chunk_id"],
        )
        return [str((p.payload or {})["chunk_id"]) for p in result.points]


def _doc_filter(doc_id: str | None) -> qm.Filter | None:
    if doc_id is None:
        return None
    return qm.Filter(must=[qm.FieldCondition(key="doc_id", match=qm.MatchValue(value=doc_id))])
