"""LLM 선정 실험. 확정한 검색 결과와 프롬프트를 고정 입력으로 후보마다 답을 받아 인용 형식, 거절, 비용, 지연을 잰다."""
import time
import asyncio
import statistics
from typing import Literal
from pydantic import BaseModel

from app.service.query.evidence_checker import EvidenceChecker
from app.service.query.citation_parser import parse_citations
from app.service.query.prompt_builder import build_messages
from app.client.llm_client import LlmClient
from app.client.llm_cache import LlmCache
from app.schema.chunk_schema import Chunk
from app.common.logger import get_logger

# 게이트웨이의 비스트리밍 출력 상한이 2,000토큰이라 그 안에서, 추론 토큰을 쓰는 모델도 답을 끝낼 만큼 둔다.
MAX_COMPLETION_TOKENS = 1500
MIN_FORMAT_COMPLIANCE = 0.95
MAX_FALSE_REFUSAL = 0.10

logger = get_logger(__name__)


class LlmCandidate(BaseModel):
    """후보 모델. 단가는 100만 토큰당 원화다. temperature를 고정할 수 없는 모델은 seed를 여러 개 두고, seed를 거부하는 모델은 None 하나를 둔다."""

    name: str
    input_krw_per_mtok: float
    output_krw_per_mtok: float
    temperature: float | None
    seeds: list[int | None]


class RetrievedItem(BaseModel):
    """확정 검색 구성으로 미리 찾아 둔 문항 하나의 근거. 모든 후보가 같은 입력을 받는다."""

    item_id: str
    language: str
    type: str
    answerable: bool
    question: str
    top_score: float
    chunks: list[Chunk]


class LlmAnswer(BaseModel):
    """후보 하나, 문항 하나, seed 하나의 결과. 검색 단계에서 거절된 문항은 LLM을 부르지 않아 토큰과 지연이 0이다."""

    model: str
    item_id: str
    language: str
    type: str
    answerable: bool
    seed: int | None
    stage: Literal["retrieval", "generation"]
    refused: bool
    format_ok: bool
    text: str
    citations: list[int]
    dropped_citations: int
    input_tokens: int
    output_tokens: int
    latency_ms: float


class LlmRun(BaseModel):
    """후보 하나, 언어 하나의 요약. 형식 준수율과 지운 인용 비율은 LLM이 실제로 답한 응답만으로 잰다."""

    model: str
    language: str
    generated: int
    format_compliance: float
    dropped_citation_rate: float
    answerable_false_refusal: float
    unanswerable_refusal: float
    cost_krw_per_item: float
    latency_ms_mean: float
    latency_ms_p95: float


class LlmVerdict(BaseModel):
    """품질 하한을 넘은 후보와 그중 문항당 비용이 가장 낮은 후보."""

    passed: list[str]
    chosen: str | None


class LlmBenchmark:
    """검색 단계 거절은 임계값으로, 생성 단계 거절은 근거 부족 토큰으로 판정한다. 동시 호출 수는 세마포어로 묶는다."""

    def __init__(self, checker: EvidenceChecker, cache: LlmCache, concurrency: int) -> None:
        self._checker = checker
        self._cache = cache
        self._semaphore = asyncio.Semaphore(concurrency)

    async def run(self, llm: LlmClient, candidate: LlmCandidate, items: list[RetrievedItem]) -> list[LlmAnswer]:
        """문항 순서, seed 순서대로 결과를 돌려준다."""
        jobs = [self._answer(llm, candidate, item, seed) for item in items for seed in candidate.seeds]
        return list(await asyncio.gather(*jobs))

    async def _answer(self, llm: LlmClient, candidate: LlmCandidate, item: RetrievedItem, seed: int | None) -> LlmAnswer:
        base = {"model": candidate.name, "item_id": item.item_id, "language": item.language, "type": item.type,
                "answerable": item.answerable, "seed": seed}
        if not self._checker.has_evidence(item.top_score):
            return LlmAnswer(**base, stage="retrieval", refused=True, format_ok=True, text="", citations=[],
                             dropped_citations=0, input_tokens=0, output_tokens=0, latency_ms=0.0)
        messages = build_messages(item.question, item.chunks)
        key = LlmCache.key(candidate.name, messages, seed, candidate.temperature, MAX_COMPLETION_TOKENS)
        cached = self._cache.get(key)
        if cached is None:
            async with self._semaphore:
                started = time.perf_counter()
                completion = await llm.complete(messages, seed=seed, max_completion_tokens=MAX_COMPLETION_TOKENS,
                                                temperature=candidate.temperature)
                latency_ms = (time.perf_counter() - started) * 1000
            self._cache.put(key, completion, latency_ms)
            logger.info("llm_answered", model=candidate.name, item=item.item_id, language=item.language, seed=seed)
        else:
            completion, latency_ms = cached
        refused = self._checker.is_insufficient(completion.text)
        parsed = parse_citations(completion.text, len(item.chunks))
        format_ok = completion.text.strip() == "INSUFFICIENT_CONTEXT" if refused else bool(parsed.citations)
        return LlmAnswer(**base, stage="generation", refused=refused, format_ok=format_ok, text=completion.text,
                         citations=parsed.citations, dropped_citations=parsed.dropped, input_tokens=completion.input_tokens,
                         output_tokens=completion.output_tokens, latency_ms=round(latency_ms, 1))


def summarize_llm(candidate: LlmCandidate, answers: list[LlmAnswer]) -> list[LlmRun]:
    """언어별 요약. 비용과 지연은 검색 단계 거절(0원, 0ms)까지 포함한 문항당 값이다."""
    runs = []
    for language in sorted({a.language for a in answers}):
        group = [a for a in answers if a.language == language]
        generated = [a for a in group if a.stage == "generation"]
        cited = sum(len(a.citations) + a.dropped_citations for a in generated)
        latencies = sorted(a.latency_ms for a in generated) or [0.0]
        cost = [a.input_tokens * candidate.input_krw_per_mtok / 1e6 + a.output_tokens * candidate.output_krw_per_mtok / 1e6 for a in group]
        runs.append(LlmRun(
            model=candidate.name, language=language, generated=len(generated),
            format_compliance=_rate([a.format_ok for a in generated]),
            dropped_citation_rate=round(sum(a.dropped_citations for a in generated) / cited, 4) if cited else 0.0,
            answerable_false_refusal=_rate([a.refused for a in group if a.answerable]),
            unanswerable_refusal=_rate([a.refused for a in group if not a.answerable]),
            cost_krw_per_item=round(statistics.fmean(cost), 4),
            latency_ms_mean=round(statistics.fmean(latencies), 1),
            latency_ms_p95=latencies[min(len(latencies) - 1, int(0.95 * len(latencies)))],
        ))
    return runs


def pick_llm(runs: list[LlmRun]) -> LlmVerdict:
    """모든 언어에서 형식 준수율 95% 이상, 답 있는 문항 오거절 10% 이하인 후보 중 문항당 평균 비용이 가장 낮은 후보."""
    models = list(dict.fromkeys(r.model for r in runs))
    passed = [
        m for m in models
        if all(r.format_compliance >= MIN_FORMAT_COMPLIANCE and r.answerable_false_refusal <= MAX_FALSE_REFUSAL for r in runs if r.model == m)
    ]
    cost = {m: statistics.fmean(r.cost_krw_per_item for r in runs if r.model == m) for m in passed}
    return LlmVerdict(passed=passed, chosen=min(passed, key=lambda m: (cost[m], models.index(m))) if passed else None)


def _rate(flags: list[bool]) -> float:
    return round(statistics.fmean(flags), 4) if flags else 0.0
