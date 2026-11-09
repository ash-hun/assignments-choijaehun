"""fusion_eval 기능의 파이프라인 통합 테스트. 같은 문항을 dense와 융합 검색으로 평가하고 짝지은 비교를 낸다."""
import asyncio
from typing import Any
from collections.abc import AsyncIterator

from tests.integ.memory_backend import MemoryChunkRepository, MemoryEmbeddingClient, MemoryEvalRecordRepository
from app.service.eval.fusion_comparator import item_values, paired_diff, retrieval_refusals
from app.client.llm_client import LlmDelta, ChatMessage, LlmClient, LlmCompletion
from app.service.query.chunk_retriever import FusionSettings, ChunkRetriever
from app.schema.gold_schema import GoldItem, GoldType, GoldEvidence
from app.service.eval.eval_service import TokenPrice, EvalService
from app.service.query.evidence_checker import EvidenceChecker
from app.service.ingest.sparse_encoder import SparseEncoder
from app.service.query.query_service import QueryService
from app.common.text_tokenizer import TextTokenizer
from app.schema.vector_schema import IndexContract
from app.schema.query_schema import RetrievalMode
from app.service.query.llm_gate import LlmGate
from app.schema.eval_schema import EvalConfig
from app.schema.chunk_schema import Chunk

DOCS = {
    "cache.md": "The cache directory defaults to the user cache folder and can be moved with UV_CACHE_DIR.",
    "lock.md": "The lockfile records exact resolved versions so installs are reproducible across machines.",
    "python.md": "Use uv python install to fetch a managed interpreter for the project.",
}
COLLECTION = "chunks_test"


class EchoLlm(LlmClient):
    def __init__(self) -> None:
        pass

    @property
    def model(self) -> str:
        return "echo"

    async def complete(self, messages: list[ChatMessage], seed: int | None, max_completion_tokens: int,
                       temperature: float | None = None, json_schema: dict[str, Any] | None = None) -> LlmCompletion:
        raise AssertionError("evaluation uses the streaming path")

    async def stream(self, messages: list[ChatMessage], seed: int | None, max_completion_tokens: int,
                     temperature: float | None = None, json_schema: dict[str, Any] | None = None) -> AsyncIterator[LlmDelta | LlmCompletion]:
        yield LlmDelta(text="See [1].")
        yield LlmCompletion(text="See [1].", model="echo", input_tokens=100, output_tokens=3)


def gold(n: int, question: str, docs: list[str]) -> GoldItem:
    type_: GoldType = "multi_doc" if len(docs) > 1 else "factual"
    return GoldItem(id=GoldItem.make_id("test", type_, n), split="test", type=type_, question=question, answerable=True,
                    reference_answer="x", evidence=[GoldEvidence(doc_id=d, quote=DOCS[d]) for d in docs], origin="human_written",
                    language="en")


ITEMS = [gold(1, "How do I move the cache with UV_CACHE_DIR and record exact resolved versions?", ["cache.md", "lock.md"]),
         gold(2, "Where is the cache directory?", ["cache.md"])]


def evaluate(mode: RetrievalMode) -> list[Any]:
    repository, embedding, encoder = MemoryChunkRepository(), MemoryEmbeddingClient(), SparseEncoder(TextTokenizer("word"))
    chunks = [Chunk(chunk_id=Chunk.make_id(d, t), doc_id=d, ordinal=0, text=t, title=d) for d, t in DOCS.items()]

    async def run() -> list[Any]:
        await repository.ensure_collection(COLLECTION, 256, IndexContract(embedding_model="m", tokenizer="word", chunk_config_hash="c"))
        await repository.upsert(COLLECTION, chunks, embedding.embed_documents([c.text for c in chunks]),
                                encoder.encode_documents([c.text for c in chunks]))
        retriever = ChunkRetriever(repository, embedding, COLLECTION, encoder, FusionSettings(mode=mode, pool=3))
        service = QueryService(retriever, EvidenceChecker(0.1), EchoLlm(), LlmGate(2, 1.0), "memory", 1, 0.0, None, 100)
        config = EvalConfig(name="t", gold_files=["g"], top_k=1, retrieval_depth=2, retrieval_mode=mode)
        outcome = await EvalService(service, retriever, MemoryEvalRecordRepository(), TokenPrice(input_krw_per_mtok=1.0,
                                    output_krw_per_mtok=1.0)).run(f"run-{mode}", "cfg", config, ITEMS, chunks)
        return outcome.records

    return asyncio.run(run())


def test_fusion_runs_are_paired_by_item_and_keep_the_same_retrieval_refusals() -> None:
    modes: tuple[RetrievalMode, ...] = ("dense", "rrf", "cc")
    runs = {mode: evaluate(mode) for mode in modes}
    values = {mode: [item_values(r, None) for r in records] for mode, records in runs.items()}

    diff = paired_diff("rrf", values["rrf"], "dense", values["dense"], "recall_at_5", 0.9875)

    assert diff.pairs == 2 and diff.verdict is not None
    assert all(r.top_score == d.top_score for r, d in zip(sorted(runs["rrf"], key=lambda r: r.record_id),
                                                          sorted(runs["dense"], key=lambda r: r.record_id)))
    assert retrieval_refusals(runs["cc"]) == retrieval_refusals(runs["dense"])
