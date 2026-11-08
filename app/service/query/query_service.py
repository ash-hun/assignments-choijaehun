"""질의응답 파이프라인 조립. 검색, 점수 거절, 프롬프트, 생성, 근거 부족 토큰 거절, 인용 변환 순서로 돈다."""
import time
from collections.abc import AsyncGenerator

from app.schema.query_schema import Citation, QueryMeta, TokenUsage, StreamToken, QueryResponse, RetrievedChunk
from app.service.query.prompt_builder import INSUFFICIENT_CONTEXT, build_messages
from app.service.query.evidence_checker import EvidenceChecker
from app.service.query.citation_parser import parse_citations
from app.service.query.chunk_retriever import ChunkRetriever
from app.client.llm_client import LlmClient, LlmCompletion
from app.common.upstream_error import LlmFailureError
from app.service.query.llm_gate import LlmGate
from app.common.logger import get_logger

REFUSAL_ANSWER = "문서에서 이 질문의 근거를 찾지 못해 답하지 않습니다. (No supporting evidence was found in the indexed documents.)"
SNIPPET_CHARS = 300

logger = get_logger(__name__)


class QueryService:
    """저장소에 쓰지 않는다. 같은 질문과 같은 인덱스면 검색 결과가 같다."""

    def __init__(
        self, retriever: ChunkRetriever, checker: EvidenceChecker, llm: LlmClient, gate: LlmGate,
        embedding_model: str, default_top_k: int, temperature: float | None, seed: int | None, max_tokens: int,
    ) -> None:
        self._retriever = retriever
        self._checker = checker
        self._llm = llm
        self._gate = gate
        self._embedding_model = embedding_model
        self._default_top_k = default_top_k
        self._temperature = temperature
        self._seed = seed
        self._max_tokens = max_tokens

    async def answer(self, question: str, top_k: int | None = None) -> QueryResponse:
        """dense 최고 점수가 임계값 미만이면 LLM을 부르지 않고 거절한다."""
        started = time.perf_counter()
        hits, scores = await self._retrieve(question, top_k)
        retrieval_ms = _elapsed_ms(started)
        if not self._checker.has_evidence(hits[0].score if hits else None):
            return self._refusal(scores, started, TokenUsage(), None, retrieval_ms)
        async with self._gate.slot():
            completion = await self._llm.complete(
                build_messages(question, [h.chunk for h in hits]), seed=self._seed,
                max_completion_tokens=self._max_tokens, temperature=self._temperature,
            )
        return self._finish(completion, hits, scores, started, None, retrieval_ms)

    async def answer_stream(self, question: str, top_k: int | None = None) -> AsyncGenerator[StreamToken | QueryResponse, None]:
        """answer와 같은 판정을 하고, 생성 텍스트를 StreamToken으로 흘린 뒤 마지막에 QueryResponse를 한 번 낸다.

        근거 부족 토큰이 클라이언트에 새지 않도록, 앞부분이 그 토큰의 접두어인 동안은 흘리지 않고 모아 둔다.
        """
        started = time.perf_counter()
        hits, scores = await self._retrieve(question, top_k)
        retrieval_ms = _elapsed_ms(started)
        if not self._checker.has_evidence(hits[0].score if hits else None):
            yield self._refusal(scores, started, TokenUsage(), None, retrieval_ms)
            return
        held = ""
        first_token_ms: int | None = None
        completion: LlmCompletion | None = None
        async with self._gate.slot():
            stream = self._llm.stream(build_messages(question, [h.chunk for h in hits]), seed=self._seed,
                                      max_completion_tokens=self._max_tokens, temperature=self._temperature)
            async for item in stream:
                if isinstance(item, LlmCompletion):
                    completion = item
                    continue
                if first_token_ms is None and INSUFFICIENT_CONTEXT.startswith((held + item.text).lstrip()):
                    held += item.text
                    continue
                if first_token_ms is None:
                    first_token_ms = _elapsed_ms(started)
                    logger.info("query_first_token", first_token_ms=first_token_ms)
                yield StreamToken(text=held + item.text)
                held = ""
        if completion is None:
            raise LlmFailureError("llm stream ended without a completion")
        yield self._finish(completion, hits, scores, started, first_token_ms, retrieval_ms)

    async def _retrieve(self, question: str, top_k: int | None) -> tuple[list[RetrievedChunk], list[float]]:
        hits = await self._retriever.retrieve(question, top_k or self._default_top_k)
        scores = [round(h.score, 4) for h in hits]
        if not self._checker.has_evidence(hits[0].score if hits else None):
            logger.info("query_refused", stage="retrieval", top_score=scores[0] if scores else None)
        return hits, scores

    def _finish(
        self, completion: LlmCompletion, hits: list[RetrievedChunk], scores: list[float], started: float, first_token_ms: int | None,
        retrieval_ms: int,
    ) -> QueryResponse:
        usage = TokenUsage(input_tokens=completion.input_tokens, output_tokens=completion.output_tokens)
        if self._checker.is_insufficient(completion.text):
            logger.info("query_refused", stage="generation", top_score=scores[0])
            return self._refusal(scores, started, usage, first_token_ms, retrieval_ms)
        return self._answered(completion, hits, scores, started, usage, first_token_ms, retrieval_ms)

    def _answered(
        self, completion: LlmCompletion, hits: list[RetrievedChunk], scores: list[float], started: float, usage: TokenUsage,
        first_token_ms: int | None, retrieval_ms: int,
    ) -> QueryResponse:
        parsed = parse_citations(completion.text, len(hits))
        citations = [_citation(n, hits[n - 1]) for n in parsed.citations]
        logger.info("query_answered", citations=len(citations), dropped=parsed.dropped, **usage.model_dump())
        return QueryResponse(status="answered", answer=parsed.text, citations=citations,
                             meta=self._meta(scores, parsed.dropped, started, usage, first_token_ms, retrieval_ms))

    def _refusal(
        self, scores: list[float], started: float, usage: TokenUsage, first_token_ms: int | None, retrieval_ms: int,
    ) -> QueryResponse:
        return QueryResponse(status="insufficient_context", answer=REFUSAL_ANSWER, citations=[],
                             meta=self._meta(scores, 0, started, usage, first_token_ms, retrieval_ms))

    def _meta(
        self, scores: list[float], dropped: int, started: float, usage: TokenUsage, first_token_ms: int | None, retrieval_ms: int,
    ) -> QueryMeta:
        return QueryMeta(model=self._llm.model, embedding_model=self._embedding_model, retrieval_scores=scores,
                         dropped_citations=dropped, latency_ms=_elapsed_ms(started), retrieval_ms=retrieval_ms, usage=usage,
                         first_token_ms=first_token_ms)


def _citation(ref: int, hit: RetrievedChunk) -> Citation:
    chunk = hit.chunk
    return Citation(ref=ref, doc_id=chunk.doc_id, title=chunk.title, url=chunk.url, chunk_id=chunk.chunk_id,
                    snippet=chunk.text[:SNIPPET_CHARS])


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
