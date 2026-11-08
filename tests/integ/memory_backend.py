"""통합 테스트용 메모리 대체 객체. 임베딩은 단어 주머니 해시 벡터, 벡터 DB는 dict라 네트워크와 모델 파일 없이 돈다."""
import re
import zlib
import numpy as np

from app.repository.qdrant_chunk_repository import QdrantChunkRepository
from app.schema.vector_schema import SparseTerms, IndexContract
from app.client.embedding_client import EmbeddingClient
from app.common.upstream_error import VectorStoreError
from app.schema.chunk_schema import Chunk

WORD = re.compile(r"\w+")


class MemoryEmbeddingClient(EmbeddingClient):
    def __init__(self) -> None:
        pass

    @property
    def model_name(self) -> str:
        return "memory-bag-of-words"

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return self._vectors(texts)

    def embed_queries(self, texts: list[str]) -> np.ndarray:
        return self._vectors(texts)

    def token_count(self, text: str) -> int:
        return len(WORD.findall(text)) + 1

    def token_offsets(self, text: str) -> list[tuple[int, int]]:
        return [m.span() for m in WORD.finditer(text)]

    def _vectors(self, texts: list[str]) -> np.ndarray:
        vectors = np.zeros((len(texts), 256), dtype=np.float32)
        for row, text in enumerate(texts):
            for word in WORD.findall(text.lower()):
                vectors[row, zlib.crc32(word.encode()) % 256] += 1.0
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        normalized: np.ndarray = vectors / np.where(norms == 0, 1, norms)
        return normalized


class MemoryChunkRepository(QdrantChunkRepository):
    def __init__(self) -> None:
        self.collections: dict[str, dict[str, np.ndarray]] = {}
        self.chunks: dict[str, dict[str, Chunk]] = {}
        self.contracts: dict[str, IndexContract] = {}
        self.down = False

    async def ensure_collection(self, name: str, dim: int, contract: IndexContract) -> None:
        self.collections.setdefault(name, {})
        self.chunks.setdefault(name, {})
        self.contracts.setdefault(name, contract)

    async def drop_collection(self, name: str) -> None:
        self.collections.pop(name, None)
        self.chunks.pop(name, None)
        self.contracts.pop(name, None)

    async def read_contract(self, name: str) -> IndexContract | None:
        self._check()
        return self.contracts.get(name)

    async def upsert(self, name: str, chunks: list[Chunk], dense: np.ndarray, sparse: list[SparseTerms]) -> None:
        self.collections[name].update({c.chunk_id: dense[i] for i, c in enumerate(chunks)})
        self.chunks[name].update({c.chunk_id: c for c in chunks})

    async def delete_except(self, name: str, keep: set[str]) -> int:
        stale = [cid for cid in self.collections[name] if cid not in keep]
        for cid in stale:
            del self.collections[name][cid]
            del self.chunks[name][cid]
        return len(stale)

    async def search_dense(self, name: str, vector: np.ndarray, k: int, exact: bool = False, doc_id: str | None = None) -> list[str]:
        return [chunk_id for chunk_id, _ in await self.search_dense_scored(name, vector, k, exact, doc_id)]

    async def search_dense_scored(
        self, name: str, vector: np.ndarray, k: int, exact: bool = False, doc_id: str | None = None,
    ) -> list[tuple[str, float]]:
        scored = sorted(((cid, float(v @ vector)) for cid, v in self.collections[name].items()), key=lambda item: (-item[1], item[0]))
        return scored[:k]

    async def search_dense_chunks(self, name: str, vector: np.ndarray, k: int) -> list[tuple[Chunk, float]]:
        self._check()
        return [(self.chunks[name][cid], score) for cid, score in await self.search_dense_scored(name, vector, k)]

    def _check(self) -> None:
        if self.down:
            raise VectorStoreError("vector store unavailable")
