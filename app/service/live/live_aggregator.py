"""실시간 질의 기록을 대시보드용 누적 지표로 묶는다. 지표마다 누적 평균, 95% 구간, 최근 이동 창, Gold Set 기준선을 낸다."""
import math
import statistics
from typing import Literal
from datetime import datetime
from pydantic import BaseModel
from collections.abc import Callable

from app.service.eval.eval_summarizer import LanguageSummary
from app.schema.eval_schema import EvalRecord, LiveRecord
from app.service.live.live_judge_worker import sampled
from app.schema.judge_schema import RecordJudgment
from app.schema.query_schema import QueryStatus

Unit = Literal["rate", "ms", "krw", "score"]
# few: 표본이 MIN_VERDICT_N보다 적어 구간을 믿기 이르다. within: 기준선이 누적 95% 구간 안. above, below: 구간 밖.
Verdict = Literal["few", "within", "above", "below"]
JudgeState = Literal["judged", "failed", "pending", "skipped"]
# 화면의 묶음. 질의가 지나는 단계(검색, 생성)와 운영 비용으로 나눈다.
Group = Literal["retrieval", "generation", "ops"]
WINDOW = 50
MAX_POINTS = 200
# 화면이 페이지로 나눠 보여준다. snapshot 한 번에 약 35KB가 더 실린다.
RECENT = 100
MIN_VERDICT_N = 10
Z95 = 1.96
NEAR_THRESHOLD = 0.05


class SeriesPoint(BaseModel):
    """n번째 값까지의 누적 평균과 95% 구간, 최근 WINDOW개 평균."""

    n: int
    cum: float
    low: float
    high: float
    window: float


class MetricSeries(BaseModel):
    """지표 하나의 시계열. reference면 검증 조건을 통과하지 못한 참고값이다."""

    key: str
    label: str
    description: str
    group: Group
    unit: Unit
    reference: bool
    baseline: float | None
    verdict: Verdict | None
    points: list[SeriesPoint]


class RecentQuery(BaseModel):
    """최근 질의 한 건의 요약. 질문과 답 원문은 넣지 않는다.

    judge: judged(판정됨), failed(판정 실패), pending(채점 대기), skipped(거절, 표본 밖, 예산 소진으로 채점하지 않음).
    """

    request_id: str
    recorded_at: datetime
    status: QueryStatus
    refusal_stage: Literal["retrieval", "generation"] | None
    top_score: float | None
    latency_ms: int
    first_token_ms: int | None
    cost_krw: float
    judge: JudgeState
    unsupported_claim: bool | None
    citation_precision: float | None


class LiveSnapshot(BaseModel):
    """대시보드 한 화면 분량의 집계."""

    config_id: str
    records: int
    answered: int
    judged: int
    judge_spent_krw: float
    judge_limit_krw: float
    judge_exhausted: bool
    baseline_run: str | None
    metrics: list[MetricSeries]
    recent: list[RecentQuery]
    gold: list[LanguageSummary]


Extractor = Callable[[EvalRecord, RecordJudgment | None], float | None]


def _judged(item: str) -> Extractor:
    def get(r: EvalRecord, j: RecordJudgment | None) -> float | None:
        value = j.quality_items.get(item) if j is not None and not j.failed else None
        return None if value is None else float(value)
    return get


def _precision(r: EvalRecord, j: RecordJudgment | None) -> float | None:
    return j.citation_precision if j is not None and not j.failed else None


def _near(threshold: float) -> Extractor:
    def get(r: EvalRecord, j: RecordJudgment | None) -> float | None:
        return None if r.top_score is None else float(abs(r.top_score - threshold) <= NEAR_THRESHOLD)
    return get


def _generation_refusal(r: EvalRecord, j: RecordJudgment | None) -> float | None:
    # 검색 단계에서 거절된 질의는 LLM에 가지 않았으니 분모에서 뺀다.
    return None if r.refusal_stage == "retrieval" else float(r.refusal_stage == "generation")


def metric_definitions(threshold: float) -> list[tuple[str, str, str, Group, Unit, bool, Extractor]]:
    """(키, 지표명, 뜻, 묶음, 단위, 참고값 여부, 값 추출 함수). 참고값 구분은 research/gold_metric_selection.md의 구성 확정을 따른다."""
    return [
        ("refusal_retrieval", "Retrieval Refusal Rate", "검색 최고 점수가 거절 임계값보다 낮아 LLM 없이 거절한 질의 비율(전체 질의 중)",
         "retrieval", "rate", False, lambda r, j: float(r.refusal_stage == "retrieval")),
        ("near_threshold", "Near-Threshold Rate", "검색 최고 점수가 거절 임계값 ±0.05 안에 든 질의 비율",
         "retrieval", "rate", False, _near(threshold)),
        ("refusal_generation", "Generation Refusal Rate", "검색을 통과한 질의 중 LLM이 근거 부족(INSUFFICIENT_CONTEXT)으로 거절한 비율",
         "generation", "rate", False, _generation_refusal),
        ("unsupported_claim", "No Unsupported Claim", "답에 검색 근거로 뒷받침되지 않는 주장이 없는 비율",
         "generation", "rate", True, _judged("unsupported_claim")),
        ("citation_precision", "Citation Precision", "답에 단 인용 중 문장을 실제로 뒷받침하는 인용의 비율",
         "generation", "score", True, _precision),
        ("latency_ms", "Latency", "답한 질의의 요청부터 응답 끝까지 걸린 시간",
         "ops", "ms", False, lambda r, j: float(r.latency_ms) if r.status == "answered" else None),
        ("ttft_ms", "TTFT", "답한 질의의 요청부터 첫 토큰까지 걸린 시간", "ops", "ms", False,
         lambda r, j: float(r.first_token_ms) if r.status == "answered" and r.first_token_ms is not None else None),
        ("cost_krw", "Cost per Query", "질의당 답변 LLM 비용", "ops", "krw", False, lambda r, j: r.cost_krw),
    ]


def build_snapshot(
    config_id: str, live: list[LiveRecord], judged: dict[str, RecordJudgment], threshold: float,
    baseline_run: str | None, baseline_records: list[EvalRecord], baseline_judged: dict[str, RecordJudgment],
    judge_spent_krw: float, judge_limit_krw: float, judge_exhausted: bool, sample_rate: float,
    gold: list[LanguageSummary] | None = None,
) -> LiveSnapshot:
    """live는 오래된 것부터다. 같은 입력이면 같은 집계가 나온다."""
    records = [item.record for item in live]
    metrics = []
    for key, label, description, group, unit, reference, extract in metric_definitions(threshold):
        values = [v for r in records if (v := extract(r, judged.get(r.record_id))) is not None]
        base = [v for r in baseline_records if (v := extract(r, baseline_judged.get(r.record_id))) is not None]
        baseline = round(statistics.fmean(base), 4) if base else None
        points = series(values, unit)
        metrics.append(MetricSeries(key=key, label=label, description=description, group=group, unit=unit, reference=reference,
                                    baseline=baseline,
                                    verdict=verdict(points[-1] if points else None, baseline), points=points))
    recent = [_recent(item, judged.get(item.record.record_id), judge_exhausted, sample_rate) for item in reversed(live[-RECENT:])]
    return LiveSnapshot(
        config_id=config_id, records=len(records), answered=sum(r.status == "answered" for r in records),
        judged=sum(1 for r in records if r.record_id in judged and not judged[r.record_id].failed),
        judge_spent_krw=judge_spent_krw, judge_limit_krw=judge_limit_krw, judge_exhausted=judge_exhausted,
        baseline_run=baseline_run, metrics=metrics, recent=recent, gold=gold or [],
    )


def verdict(last: SeriesPoint | None, baseline: float | None) -> Verdict | None:
    """기준선이 누적 95% 구간 안에 있으면 기준선 수준으로 본다. 표본이 적으면 판정을 미룬다."""
    if last is None or baseline is None:
        return None
    if last.n < MIN_VERDICT_N:
        return "few"
    if baseline < last.low:
        return "above"
    if baseline > last.high:
        return "below"
    return "within"


def _recent(item: LiveRecord, judgment: RecordJudgment | None, exhausted: bool, sample_rate: float) -> RecentQuery:
    r = item.record
    if judgment is not None:
        state: JudgeState = "failed" if judgment.failed else "judged"
    elif r.status == "answered" and sampled(r.record_id, sample_rate) and not exhausted:
        state = "pending"
    else:
        state = "skipped"
    ok = judgment if judgment is not None and not judgment.failed else None
    return RecentQuery(
        request_id=r.record_id.removeprefix("live:"), recorded_at=item.recorded_at, status=r.status,
        refusal_stage=r.refusal_stage, top_score=r.top_score, latency_ms=r.latency_ms, first_token_ms=r.first_token_ms,
        cost_krw=r.cost_krw, judge=state, unsupported_claim=ok.quality_items.get("unsupported_claim") if ok else None,
        citation_precision=ok.citation_precision if ok else None,
    )


def series(values: list[float], unit: Unit) -> list[SeriesPoint]:
    """값마다 누적 지점을 만들되 MAX_POINTS개를 넘으면 고르게 솎는다(마지막 지점은 항상 남긴다).

    비율은 Wilson 구간, 나머지는 정규 근사 구간이다. 0~1 점수는 정규 근사 구간을 [0, 1]로 자른다. 표본이 하나면 구간은 그 값 하나다.
    """
    n_total = len(values)
    if n_total == 0:
        return []
    keep = range(1, n_total + 1) if n_total <= MAX_POINTS else sorted(
        {round(i * n_total / MAX_POINTS) for i in range(1, MAX_POINTS)} | {n_total})
    prefix = [0.0]
    squares = [0.0]
    for v in values:
        prefix.append(prefix[-1] + v)
        squares.append(squares[-1] + v * v)
    points = []
    for n in keep:
        mean = prefix[n] / n
        low, high = wilson(mean, n) if unit == "rate" else normal(mean, (squares[n] - n * mean * mean), n)
        if unit == "score":
            low, high = max(0.0, low), min(1.0, high)
        start = max(0, n - WINDOW)
        points.append(SeriesPoint(n=n, cum=round(mean, 4), low=round(low, 4), high=round(high, 4),
                                  window=round((prefix[n] - prefix[start]) / (n - start), 4)))
    return points


def wilson(p: float, n: int) -> tuple[float, float]:
    """비율 p, 표본 n의 Wilson 95% 구간. 표본이 적거나 p가 0, 1에 가까워도 구간이 [0, 1] 밖으로 나가지 않는다."""
    denom = 1 + Z95 * Z95 / n
    center = (p + Z95 * Z95 / (2 * n)) / denom
    half = Z95 * math.sqrt(p * (1 - p) / n + Z95 * Z95 / (4 * n * n)) / denom
    return max(0.0, center - half), min(1.0, center + half)


def normal(mean: float, sum_sq_dev: float, n: int) -> tuple[float, float]:
    """평균의 정규 근사 95% 구간. 매 지점 bootstrap은 지점 수만큼 반복이 늘어 실시간 갱신에 쓰지 않는다."""
    if n < 2:
        return mean, mean
    sd = math.sqrt(max(sum_sq_dev, 0.0) / (n - 1))
    half = Z95 * sd / math.sqrt(n)
    return mean - half, mean + half
