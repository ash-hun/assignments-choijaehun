"""selection_run 기능의 Chunking 선정과 Embedding 교차 확인 파이프라인 통합 테스트. 분할, 색인, 검색, 지표, 판정을 이어서 돌린다."""
import re
import zlib
import asyncio
import numpy as np

from app.service.eval.chunking_benchmark import ChunkingRun, ChunkingBenchmark, pick_best
from app.service.eval.embedding_crosscheck import ModelResult, judge, truncated_chunks
from app.repository.qdrant_chunk_repository import QdrantChunkRepository
from app.service.ingest.chunk_splitter import ChunkMethod, ChunkSplitter
from app.service.ingest.sentence_embedder import SentenceEmbedder
from app.schema.vector_schema import SparseTerms, IndexContract
from app.schema.gold_schema import GoldItem, GoldEvidence
from app.client.embedding_client import EmbeddingClient
from app.schema.chunk_schema import Chunk, Document

WORD = re.compile(r"\w+")
CACHE = "The cache directory defaults to the user cache folder and can be moved with UV_CACHE_DIR."
LOCK = "The lockfile records exact resolved versions so installs are reproducible across machines."
DOCUMENTS = [
    Document(doc_id="cache.md", title="Cache", text=f"# Cache\n\nIntro text about caching.\n\n## Location\n\n{CACHE}\n"),
    Document(doc_id="lock.md", title="Lock", text=f"# Lockfile\n\nIntro text about locking.\n\n## Purpose\n\n{LOCK}\n"),
]


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

    async def ensure_collection(self, name: str, dim: int, contract: IndexContract) -> None:
        self.collections.setdefault(name, {})

    async def drop_collection(self, name: str) -> None:
        self.collections.pop(name, None)

    async def upsert(self, name: str, chunks: list[Chunk], dense: np.ndarray, sparse: list[SparseTerms]) -> None:
        self.collections[name].update({c.chunk_id: dense[i] for i, c in enumerate(chunks)})

    async def search_dense(self, name: str, vector: np.ndarray, k: int, exact: bool = False, doc_id: str | None = None) -> list[str]:
        scored = sorted(self.collections[name].items(), key=lambda item: (-float(item[1] @ vector), item[0]))
        return [chunk_id for chunk_id, _ in scored[:k]]


def gold(language: str) -> list[GoldItem]:
    questions = {"en": ("Where is the cache directory?", "Why does the lockfile record resolved versions?"),
                 "ko": ("cache directory 위치는?", "lockfile 이 resolved versions 를 기록하는 이유는?")}[language]
    items = []
    for ordinal, (question, doc_id, quote) in enumerate(zip(questions, ("cache.md", "lock.md"), (CACHE, LOCK)), start=1):
        source = GoldItem.make_id("dev", "factual", ordinal)
        items.append(GoldItem(
            id=source if language == "en" else GoldItem.make_translation_id(source, "ko"), split="dev", type="factual",
            question=question, answerable=True, reference_answer="a", evidence=[GoldEvidence(doc_id=doc_id, quote=quote)],
            origin="llm_draft_reviewed", language=language, translation_of=None if language == "en" else source,
        ))
    return items


def run_pipeline(methods: tuple[ChunkMethod, ...]) -> tuple[list[ChunkingRun], MemoryChunkRepository, MemoryEmbeddingClient]:
    client = MemoryEmbeddingClient()
    repository = MemoryChunkRepository()
    benchmark = ChunkingBenchmark(repository, client)
    embedder = SentenceEmbedder(client)
    items = {"en": gold("en"), "ko": gold("ko")}

    async def measure() -> list[ChunkingRun]:
        runs: list[ChunkingRun] = []
        for method in methods:
            splitter = ChunkSplitter(method, 40, 0, client.token_count, client.token_offsets, embedder if method == "semantic" else None)
            chunks = [c for d in DOCUMENTS for c in splitter.split(d)]
            runs += await benchmark.run(splitter.name, chunks, items, 0.0)
        return runs

    return asyncio.run(measure()), repository, client


def test_chunking_selection_finds_whole_evidence_and_picks_the_simplest_tied_method() -> None:
    runs, repository, _ = run_pipeline(("fixed", "structure", "semantic"))

    assert all(r.hit_at_5.mean == 1.0 and r.evidence_preserved == 1.0 for r in runs)
    assert repository.collections == {}
    verdict = pick_best(runs)
    assert all(row.tied for row in verdict.rows)
    assert verdict.chosen == min(verdict.rows, key=lambda r: (r.context_tokens_mean, ["fixed", "structure", "semantic"].index(r.config.split("-")[0]))).config


def test_rerunning_the_pipeline_gives_the_same_judgements() -> None:
    first, _, _ = run_pipeline(("fixed", "semantic"))
    second, _, _ = run_pipeline(("fixed", "semantic"))

    assert [r.per_question for r in first] == [r.per_question for r in second]
    assert [(r.chunks, r.context_tokens_mean) for r in first] == [(r.chunks, r.context_tokens_mean) for r in second]


class ShortMemoryEmbeddingClient(MemoryEmbeddingClient):
    @property
    def model_name(self) -> str:
        return "memory-short"


def test_embedding_crosscheck_counts_truncation_and_judges_tied_models_by_coverage() -> None:
    repository = MemoryChunkRepository()
    incumbent, challenger = MemoryEmbeddingClient(), ShortMemoryEmbeddingClient()
    splitter = ChunkSplitter("structure", 40, 0, incumbent.token_count, incumbent.token_offsets)
    chunks = [c for d in DOCUMENTS for c in splitter.split(d)]
    items = {"en": gold("en"), "ko": gold("ko")}

    async def measure() -> tuple[ModelResult, ModelResult]:
        results = []
        for client, limit in ((incumbent, 40), (challenger, 10)):
            runs = await ChunkingBenchmark(repository, client).run(splitter.name, chunks, items, 0.0)
            results.append(ModelResult(model=client.model_name, max_input_tokens=limit,
                                       truncated_chunks=truncated_chunks(client, chunks, limit), runs=runs))
        return results[0], results[1]

    first, second = asyncio.run(measure())
    verdict = judge(first, second)

    assert (first.truncated_chunks, second.truncated_chunks > 0) == (0, True)
    assert (verdict.chosen, verdict.reason) == ("memory-short", "tied_challenger_cheaper")
    assert repository.collections == {}
