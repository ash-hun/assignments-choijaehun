"""통합 테스트용 메모리 대체 객체. 임베딩은 단어 주머니 해시 벡터, 벡터 DB는 dict라 네트워크와 모델 파일 없이 돈다."""
import re
import zlib
import numpy as np
from datetime import datetime, timedelta

from app.repository.qdrant_chunk_repository import QdrantChunkRepository
from app.schema.eval_schema import EvalRecord, LiveRecord, EvalManifest
from app.repository.eval_record_repository import EvalRecordRepository
from app.schema.vector_schema import SparseTerms, IndexContract
from app.schema.judge_schema import JudgeResult
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

    async def all_chunks(self, name: str) -> list[Chunk]:
        self._check()
        return sorted(self.chunks[name].values(), key=lambda c: c.chunk_id)

    async def search_dense_chunks(self, name: str, vector: np.ndarray, k: int) -> list[tuple[Chunk, float]]:
        self._check()
        return [(self.chunks[name][cid], score) for cid, score in await self.search_dense_scored(name, vector, k)]

    def _check(self) -> None:
        if self.down:
            raise VectorStoreError("vector store unavailable")


class MemoryEvalRecordRepository(EvalRecordRepository):
    def __init__(self) -> None:
        self.runs: dict[str, EvalManifest] = {}
        self.rows: dict[str, EvalRecord] = {}
        self.created: dict[str, datetime] = {}
        self.judged: dict[tuple[str, str, int, str, str], JudgeResult] = {}

    async def ensure_schema(self) -> None:
        pass

    async def upsert_run(self, run_id: str, manifest: EvalManifest) -> None:
        self.runs[run_id] = manifest

    async def records(self, run_id: str) -> list[EvalRecord]:
        return sorted((r for r in self.rows.values() if r.run_id == run_id), key=lambda r: r.record_id)

    async def upsert_record(self, record: EvalRecord) -> None:
        self.rows[record.record_id] = record
        self.created.setdefault(record.record_id, datetime(2026, 1, 1) + timedelta(seconds=len(self.created)))

    async def upsert_judgment(self, result: JudgeResult) -> None:
        self.judged[(result.record_id, result.kind, result.sample, result.judge_model, result.prompt_version)] = result

    async def judgments(self, run_id: str) -> list[JudgeResult]:
        ids = {r.record_id for r in self.rows.values() if r.run_id == run_id}
        return [self.judged[k] for k in sorted(self.judged) if k[0] in ids]

    async def judgments_for(self, record_ids: list[str]) -> list[JudgeResult]:
        wanted = set(record_ids)
        return [self.judged[k] for k in sorted(self.judged) if k[0] in wanted]

    async def live_records(self, config_id: str, limit: int) -> list[LiveRecord]:
        rows = [r for r in self.rows.values() if r.source == "live" and r.config_id == config_id]
        return [LiveRecord(record=r, recorded_at=self.created[r.record_id]) for r in rows[-limit:]]

    async def unjudged_live(self, config_id: str, versions: list[str], limit: int) -> list[EvalRecord]:
        done = {(k[0], k[4]) for k, v in self.judged.items() if v.ok}
        rows = [r for r in self.rows.values() if r.source == "live" and r.config_id == config_id and r.status == "answered"
                and not all((r.record_id, v) in done for v in versions)]
        return rows[:limit]

    async def live_judge_tokens(self) -> tuple[int, int]:
        live = {r.record_id for r in self.rows.values() if r.source == "live"}
        results = [v for k, v in self.judged.items() if k[0] in live]
        return sum(r.input_tokens for r in results), sum(r.output_tokens for r in results)

    async def latest_gold_run(self, config_id: str) -> str | None:
        runs = [run_id for run_id, m in self.runs.items() if m.config_id == config_id and m.config.variant == "none"]
        return runs[-1] if runs else None
