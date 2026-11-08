"""query 기능의 파이프라인 분기(점수 거절, 근거 부족 토큰 거절, 인용 변환, 스트리밍의 토큰 보류) 단위 테스트."""
import asyncio
from typing import Any
from collections.abc import AsyncIterator

from app.client.llm_client import LlmDelta, ChatMessage, LlmClient, LlmCompletion
from app.schema.query_schema import StreamToken, QueryResponse, RetrievedChunk
from app.service.query.prompt_builder import INSUFFICIENT_CONTEXT
from app.service.query.evidence_checker import EvidenceChecker
from app.service.query.chunk_retriever import ChunkRetriever
from app.service.query.query_service import QueryService
from app.service.query.llm_gate import LlmGate
from app.schema.chunk_schema import Chunk


def hit(doc_id: str, text: str, score: float) -> RetrievedChunk:
    chunk = Chunk(chunk_id=Chunk.make_id(doc_id, text), doc_id=doc_id, ordinal=0, text=text, title=doc_id.upper(), url=f"https://x/{doc_id}")
    return RetrievedChunk(chunk=chunk, score=score)


class FixedRetriever(ChunkRetriever):
    def __init__(self, hits: list[RetrievedChunk]) -> None:
        self.hits = hits

    async def retrieve(self, question: str, k: int) -> list[RetrievedChunk]:
        return self.hits[:k]


class FixedLlm(LlmClient):
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls = 0

    @property
    def model(self) -> str:
        return "fixed"

    async def complete(self, messages: list[ChatMessage], seed: int | None, max_completion_tokens: int,
                       temperature: float | None = None, json_schema: dict[str, Any] | None = None) -> LlmCompletion:
        self.calls += 1
        return LlmCompletion(text=self.text, model="fixed", input_tokens=50, output_tokens=5)

    async def stream(self, messages: list[ChatMessage], seed: int | None, max_completion_tokens: int,
                     temperature: float | None = None) -> AsyncIterator[LlmDelta | LlmCompletion]:
        self.calls += 1
        for start in range(0, len(self.text), 4):
            yield LlmDelta(text=self.text[start:start + 4])
        yield LlmCompletion(text=self.text, model="fixed", input_tokens=50, output_tokens=5)


def service(hits: list[RetrievedChunk], llm: FixedLlm) -> QueryService:
    return QueryService(FixedRetriever(hits), EvidenceChecker(0.5), llm, LlmGate(1, 1.0), "emb", 5, 0.0, None, 100)


def ask(hits: list[RetrievedChunk], llm: FixedLlm) -> QueryResponse:
    return asyncio.run(service(hits, llm).answer("q"))


def ask_stream(hits: list[RetrievedChunk], llm: FixedLlm) -> list[StreamToken | QueryResponse]:
    async def collect() -> list[StreamToken | QueryResponse]:
        return [event async for event in service(hits, llm).answer_stream("q")]

    return asyncio.run(collect())


def test_low_top_score_is_refused_without_calling_the_llm() -> None:
    llm = FixedLlm("unused [1]")

    response = ask([hit("a.md", "text", 0.3)], llm)

    assert (response.status, llm.calls, response.meta.usage.input_tokens) == ("insufficient_context", 0, 0)
    assert response.meta.retrieval_scores == [0.3]


def test_refusal_token_from_the_llm_becomes_insufficient_context_with_usage() -> None:
    response = ask([hit("a.md", "text", 0.9)], FixedLlm(INSUFFICIENT_CONTEXT))

    assert (response.status, response.citations, response.meta.usage.input_tokens) == ("insufficient_context", [], 50)


def test_citations_map_to_the_numbered_chunks_and_unknown_numbers_are_dropped() -> None:
    hits = [hit("a.md", "alpha text", 0.9), hit("b.md", "beta text", 0.8)]

    response = ask(hits, FixedLlm("Use beta [2]. Also alpha [1][5]."))

    assert response.status == "answered"
    assert response.answer == "Use beta [2]. Also alpha [1]."
    assert [(c.ref, c.doc_id, c.title, c.url) for c in response.citations] == [(2, "b.md", "B.MD", "https://x/b.md"), (1, "a.md", "A.MD", "https://x/a.md")]
    assert response.meta.dropped_citations == 1


def test_stream_sends_tokens_then_a_final_answer_built_like_the_non_stream_one() -> None:
    hits = [hit("a.md", "alpha text", 0.9), hit("b.md", "beta text", 0.8)]
    text = "Use beta [2]. Also alpha [1][5]."

    events = ask_stream(hits, FixedLlm(text))
    final = events[-1]

    assert isinstance(final, QueryResponse)
    assert "".join(e.text for e in events if isinstance(e, StreamToken)) == text
    assert final.model_dump(exclude={"meta"}) == ask(hits, FixedLlm(text)).model_dump(exclude={"meta"})
    assert final.meta.first_token_ms is not None


def test_stream_never_leaks_the_refusal_token_and_ends_with_insufficient_context() -> None:
    events = ask_stream([hit("a.md", "text", 0.9)], FixedLlm(f"  {INSUFFICIENT_CONTEXT}"))

    assert len(events) == 1
    assert isinstance(events[0], QueryResponse) and events[0].status == "insufficient_context"
