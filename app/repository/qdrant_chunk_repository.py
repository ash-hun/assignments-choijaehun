"""Qdrant에 청크와 dense, sparse 벡터를 저장하고 검색한다. 데이터베이스 선정 실험의 후보 구현이다."""
import uuid
import numpy as np
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qm
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from app.schema.vector_schema import SparseTerms, IndexContract
from app.common.upstream_error import VectorStoreError
from app.schema.chunk_schema import Chunk

# Query 경로가 쓰는 메서드는 이 예외들을 VectorStoreError로 바꿔 API 층이 503으로 매핑하게 한다.
# Query 경로는 REST로 연결해 연결 실패가 ResponseHandlingException으로 온다(gRPC 예외는 다루지 않는다).
STORE_ERRORS = (UnexpectedResponse, ResponseHandlingException, OSError)
CHUNK_FIELDS = ["chunk_id", "doc_id", "ordinal", "text", "title", "url"]
DELETE_BATCH = 256
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
        """컬렉션 metadata에서 인덱스 계약을 읽는다. 컬렉션이 없으면 None."""
        async with _store_errors():
            if not await self._client.collection_exists(name):
                return None
            info = await self._client.get_collection(name)
        metadata = info.config.metadata
        return IndexContract.model_validate(metadata) if metadata else None

    async def search_dense_chunks(self, name: str, vector: np.ndarray, k: int) -> list[tuple[Chunk, float]]:
        """코사인 유사도 상위 k개 청크와 점수. Query 경로용이라 HNSW 근사 검색을 쓴다."""
        async with _store_errors():
            result = await self._client.query_points(name, query=vector.tolist(), using=DENSE, limit=k, with_payload=CHUNK_FIELDS)
        return [(Chunk.model_validate(p.payload or {}), float(p.score)) for p in result.points]

    async def all_chunks(self, name: str) -> list[Chunk]:
        """컬렉션의 청크 전부를 chunk_id 순으로. 평가에서 근거 구절마다 인덱스 전체의 관련 청크 수를 셀 때 쓴다."""
        chunks: list[Chunk] = []
        offset: qm.ExtendedPointId | None = None
        async with _store_errors():
            while True:
                points, offset = await self._client.scroll(name, limit=DELETE_BATCH, offset=offset, with_payload=CHUNK_FIELDS)
                chunks += [Chunk.model_validate(p.payload or {}) for p in points]
                if offset is None:
                    break
        return sorted(chunks, key=lambda c: c.chunk_id)

    async def delete_except(self, name: str, keep: set[str]) -> int:
        """keep에 없는 chunk_id의 포인트를 지운다. 원문이 바뀌어 사라진 청크를 남기지 않아 재실행 결과가 같은 상태로 수렴한다."""
        stale: list[qm.ExtendedPointId] = []
        offset: qm.ExtendedPointId | None = None
        while True:
            points, offset = await self._client.scroll(name, limit=DELETE_BATCH, offset=offset, with_payload=["chunk_id"])
            stale += [p.id for p in points if (p.payload or {}).get("chunk_id") not in keep]
            if offset is None:
                break
        for start in range(0, len(stale), DELETE_BATCH):
            await self._client.delete(name, points_selector=qm.PointIdsList(points=stale[start:start + DELETE_BATCH]), wait=True)
        return len(stale)

    async def upsert(self, name: str, chunks: list[Chunk], dense: np.ndarray, sparse: list[SparseTerms]) -> None:
        """chunk_id에서 계산한 포인트 id로 덮어쓴다."""
        for start in range(0, len(chunks), UPSERT_BATCH):
            points = [
                qm.PointStruct(
                    id=str(uuid.uuid5(POINT_NAMESPACE, chunk.chunk_id)),
                    vector={DENSE: dense[i].tolist(), SPARSE: qm.SparseVector(indices=sparse[i].indices, values=sparse[i].values)},
                    payload=chunk.model_dump(include=set(CHUNK_FIELDS)),
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
        return [chunk_id for chunk_id, _ in await self.search_dense_scored(name, vector, k, exact, doc_id)]

    async def search_dense_scored(
        self, name: str, vector: np.ndarray, k: int, exact: bool = False, doc_id: str | None = None,
    ) -> list[tuple[str, float]]:
        """상위 k개 (chunk_id, 코사인 유사도). 거절 판정은 검색 방식과 상관없이 이 dense 점수를 쓴다."""
        result = await self._client.query_points(
            name, query=vector.tolist(), using=DENSE, limit=k, with_payload=["chunk_id"],
            search_params=qm.SearchParams(exact=exact), query_filter=_doc_filter(doc_id),
        )
        return [(str((p.payload or {})["chunk_id"]), float(p.score)) for p in result.points]

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


@asynccontextmanager
async def _store_errors() -> AsyncIterator[None]:
    try:
        yield
    except STORE_ERRORS as error:
        raise VectorStoreError("vector store unavailable") from error
