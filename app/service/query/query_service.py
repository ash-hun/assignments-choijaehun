"""질의응답 파이프라인 조립. 검색, 점수 거절, 프롬프트, 생성, 근거 부족 토큰 거절, 인용 변환 순서로 돈다."""
import time

from app.schema.query_schema import Citation, QueryMeta, TokenUsage, QueryResponse, RetrievedChunk
from app.service.query.evidence_checker import EvidenceChecker
from app.service.query.citation_parser import parse_citations
from app.service.query.chunk_retriever import ChunkRetriever
from app.service.query.prompt_builder import build_messages
from app.client.llm_client import LlmClient, LlmCompletion
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
        hits = await self._retriever.retrieve(question, top_k or self._default_top_k)
        scores = [round(h.score, 4) for h in hits]
        if not self._checker.has_evidence(hits[0].score if hits else None):
            logger.info("query_refused", stage="retrieval", top_score=scores[0] if scores else None)
            return self._refusal(scores, started, TokenUsage())

        async with self._gate.slot():
            completion = await self._llm.complete(
                build_messages(question, [h.chunk for h in hits]), seed=self._seed,
                max_completion_tokens=self._max_tokens, temperature=self._temperature,
            )
        usage = TokenUsage(input_tokens=completion.input_tokens, output_tokens=completion.output_tokens)
        if self._checker.is_insufficient(completion.text):
            logger.info("query_refused", stage="generation", top_score=scores[0])
            return self._refusal(scores, started, usage)
        return self._answered(completion, hits, scores, started, usage)

    def _answered(self, completion: LlmCompletion, hits: list[RetrievedChunk], scores: list[float], started: float, usage: TokenUsage) -> QueryResponse:
        parsed = parse_citations(completion.text, len(hits))
        citations = [_citation(n, hits[n - 1]) for n in parsed.citations]
        logger.info("query_answered", citations=len(citations), dropped=parsed.dropped, **usage.model_dump())
        return QueryResponse(status="answered", answer=parsed.text, citations=citations,
                             meta=self._meta(scores, parsed.dropped, started, usage))

    def _refusal(self, scores: list[float], started: float, usage: TokenUsage) -> QueryResponse:
        return QueryResponse(status="insufficient_context", answer=REFUSAL_ANSWER, citations=[],
                             meta=self._meta(scores, 0, started, usage))

    def _meta(self, scores: list[float], dropped: int, started: float, usage: TokenUsage) -> QueryMeta:
        return QueryMeta(model=self._llm.model, embedding_model=self._embedding_model, retrieval_scores=scores,
                         dropped_citations=dropped, latency_ms=int((time.perf_counter() - started) * 1000), usage=usage)


def _citation(ref: int, hit: RetrievedChunk) -> Citation:
    chunk = hit.chunk
    return Citation(ref=ref, doc_id=chunk.doc_id, title=chunk.title, url=chunk.url, chunk_id=chunk.chunk_id,
                    snippet=chunk.text[:SNIPPET_CHARS])
