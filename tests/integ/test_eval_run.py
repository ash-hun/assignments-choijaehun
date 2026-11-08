"""eval_run 기능의 파이프라인 통합 테스트. 실제 질의 경로(검색, 거절, 스트리밍 생성)에 메모리 저장소와 대체 LLM을 넣어 돌린다."""
import asyncio
from typing import Any
from pathlib import Path
from collections.abc import AsyncIterator

from tests.integ.memory_backend import MemoryChunkRepository, MemoryEmbeddingClient, MemoryEvalRecordRepository
from app.client.llm_client import LlmDelta, ChatMessage, LlmClient, LlmCompletion
from app.service.eval.eval_service import TokenPrice, EvalOutcome, EvalService
from app.schema.gold_schema import GoldItem, GoldType, GoldEvidence
from app.service.eval.eval_summarizer import summarize_records
from app.service.query.evidence_checker import EvidenceChecker
from app.service.query.chunk_retriever import ChunkRetriever
from app.schema.eval_schema import EvalConfig, EvalManifest
from app.service.query.query_service import QueryService
from app.service.eval.report_writer import write_report
from app.common.upstream_error import LlmFailureError
from app.schema.vector_schema import IndexContract
from app.service.query.llm_gate import LlmGate
from app.schema.chunk_schema import Chunk

CACHE = "The cache directory defaults to the user cache folder and can be moved with UV_CACHE_DIR."
LOCK = "The lockfile records exact resolved versions so installs are reproducible across machines."
COLLECTION = "chunks_test"
PRICE = TokenPrice(input_krw_per_mtok=100.0, output_krw_per_mtok=1000.0)


class CountingLlm(LlmClient):
    def __init__(self) -> None:
        self.calls = 0
        self.failure: Exception | None = None

    @property
    def model(self) -> str:
        return "counting"

    async def complete(self, messages: list[ChatMessage], seed: int | None, max_completion_tokens: int,
                       temperature: float | None = None, json_schema: dict[str, Any] | None = None) -> LlmCompletion:
        raise AssertionError("evaluation uses the streaming path")

    async def stream(self, messages: list[ChatMessage], seed: int | None, max_completion_tokens: int,
                     temperature: float | None = None) -> AsyncIterator[LlmDelta | LlmCompletion]:
        self.calls += 1
        if self.failure:
            raise self.failure
        for piece in ("Move it with ", "UV_CACHE_DIR [1] ", "and [9]."):
            yield LlmDelta(text=piece)
        yield LlmCompletion(text="Move it with UV_CACHE_DIR [1] and [9].", model="counting", input_tokens=1000, output_tokens=11)


def gold(n: int, question: str, evidence: list[GoldEvidence]) -> GoldItem:
    answerable = bool(evidence)
    type_: GoldType = "factual" if answerable else "unanswerable"
    return GoldItem(id=GoldItem.make_id("test", type_, n), split="test", type=type_, question=question, answerable=answerable,
                    reference_answer="UV_CACHE_DIR" if answerable else "", evidence=evidence, origin="human_written",
                    acceptance_criteria=["names UV_CACHE_DIR"])


def build() -> tuple[EvalService, MemoryEvalRecordRepository, CountingLlm, list[Chunk]]:
    repository, embedding, llm = MemoryChunkRepository(), MemoryEmbeddingClient(), CountingLlm()
    chunks = [Chunk(chunk_id=Chunk.make_id(d, t), doc_id=d, ordinal=0, text=t, title=d) for d, t in (("cache.md", CACHE), ("lock.md", LOCK))]

    async def index() -> None:
        await repository.ensure_collection(COLLECTION, 256, IndexContract(embedding_model="m", tokenizer="word", chunk_config_hash="c"))
        await repository.upsert(COLLECTION, chunks, embedding.embed_documents([c.text for c in chunks]), [])

    asyncio.run(index())
    retriever = ChunkRetriever(repository, embedding, COLLECTION)
    service = QueryService(retriever, EvidenceChecker(0.3), llm, LlmGate(2, 1.0), "memory", 2, 0.0, None, 100)
    records = MemoryEvalRecordRepository()
    return EvalService(service, retriever, records, PRICE), records, llm, chunks


ITEMS = [
    gold(1, "Where is the uv cache directory and how do I move it?", [GoldEvidence(doc_id="cache.md", quote=CACHE)]),
    gold(2, "What is the weather on Mars?", []),
]
CONFIG = EvalConfig(name="t", gold_files=["g"], top_k=2, retrieval_depth=2, concurrency=2)


def run(service: EvalService, chunks: list[Chunk]) -> EvalOutcome:
    return asyncio.run(service.run("t-run", "cfg", CONFIG, ITEMS, chunks))


def test_eval_records_retrieval_refusal_and_cost_then_reuses_records_without_calling_the_llm(tmp_path: Path) -> None:
    service, records, llm, chunks = build()

    first = run(service, chunks)
    calls_after_first = llm.calls
    second = run(service, chunks)

    answered, refused = sorted(first.records, key=lambda r: r.type or "")
    assert answered.status == "answered" and answered.dropped_citations == 1 and answered.first_token_ms is not None
    assert answered.rank is not None and answered.rank.recall_at_5 == 1.0
    assert answered.cost_krw == round(1000 * 100 / 1e6 + 11 * 1000 / 1e6, 4)
    assert refused.status == "insufficient_context" and refused.refusal_stage == "retrieval" and refused.rank is None
    assert calls_after_first == 1 and llm.calls == 1
    assert second.reused == 2 and second.records == first.records

    manifest = EvalManifest(
        config=CONFIG, config_id="cfg", gold_hashes={}, corpus_manifest_hash="m", index_contract={}, collection=COLLECTION,
        answer_model="counting", answer_temperature=0.0, answer_seed=None, answer_max_tokens=100, refusal_threshold=0.3,
        prompt_hash="p", bootstrap_seed=2026, git_commit="abc",
    )
    for _ in range(2):
        write_report(tmp_path, "t-run", manifest, second.records, summarize_records(second.records, 0.3), second.failed)
    summary = (tmp_path / "t-run" / "summary.md").read_text(encoding="utf-8")
    assert "Recall@5" in summary and "TTFT" in summary
    assert len((tmp_path / "t-run" / "results.jsonl").read_text(encoding="utf-8").splitlines()) == 2


def test_failed_items_are_not_recorded_and_the_next_run_fills_them() -> None:
    service, records, llm, chunks = build()
    llm.failure = LlmFailureError("upstream down")

    first = run(service, chunks)
    llm.failure = None
    second = run(service, chunks)

    assert first.failed == [str(ITEMS[0].id)] and len(first.records) == 1
    assert second.failed == [] and second.reused == 1 and len(second.records) == 2
