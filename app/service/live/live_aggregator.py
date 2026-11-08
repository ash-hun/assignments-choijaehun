"""실시간 질의 기록을 대시보드용 누적 지표로 묶는다. 지표마다 누적 평균, 95% 구간, 최근 이동 창, Gold Set 기준선을 낸다."""
import math
import statistics
from typing import Literal
from pydantic import BaseModel
from collections.abc import Callable

from app.schema.judge_schema import RecordJudgment
from app.schema.eval_schema import EvalRecord

Unit = Literal["rate", "ms", "krw", "score"]
WINDOW = 50
MAX_POINTS = 200
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
    unit: Unit
    reference: bool
    baseline: float | None
    points: list[SeriesPoint]


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


def metric_definitions(threshold: float) -> list[tuple[str, str, Unit, bool, Extractor]]:
    """(키, 표시 이름, 단위, 참고값 여부, 값 추출 함수). 참고값 구분은 research/gold_metric_selection.md의 구성 확정을 따른다."""
    return [
        ("refusal_rate", "거절률", "rate", False, lambda r, j: float(r.status == "insufficient_context")),
        ("near_threshold", "검색 최고 점수가 임계값 ±0.05 안", "rate", False, _near(threshold)),
        ("latency_ms", "Latency(답한 질의)", "ms", False, lambda r, j: float(r.latency_ms) if r.status == "answered" else None),
        ("ttft_ms", "TTFT(답한 질의)", "ms", False,
         lambda r, j: float(r.first_token_ms) if r.status == "answered" and r.first_token_ms is not None else None),
        ("cost_krw", "질의당 비용", "krw", False, lambda r, j: r.cost_krw),
        ("unsupported_claim", "근거 없는 주장 없음(참고값)", "rate", True, _judged("unsupported_claim")),
        ("citation_precision", "Citation Precision(참고값)", "score", True, _precision),
    ]


def build_snapshot(
    config_id: str, records: list[EvalRecord], judged: dict[str, RecordJudgment], threshold: float,
    baseline_run: str | None, baseline_records: list[EvalRecord], baseline_judged: dict[str, RecordJudgment],
    judge_spent_krw: float, judge_limit_krw: float, judge_exhausted: bool,
) -> LiveSnapshot:
    """records는 오래된 것부터다. 같은 입력이면 같은 집계가 나온다."""
    metrics = []
    for key, label, unit, reference, extract in metric_definitions(threshold):
        values = [v for r in records if (v := extract(r, judged.get(r.record_id))) is not None]
        base = [v for r in baseline_records if (v := extract(r, baseline_judged.get(r.record_id))) is not None]
        metrics.append(MetricSeries(
            key=key, label=label, unit=unit, reference=reference,
            baseline=round(statistics.fmean(base), 4) if base else None, points=series(values, unit == "rate"),
        ))
    return LiveSnapshot(
        config_id=config_id, records=len(records), answered=sum(r.status == "answered" for r in records),
        judged=sum(1 for r in records if r.record_id in judged and not judged[r.record_id].failed),
        judge_spent_krw=judge_spent_krw, judge_limit_krw=judge_limit_krw, judge_exhausted=judge_exhausted,
        baseline_run=baseline_run, metrics=metrics,
    )


def series(values: list[float], is_rate: bool) -> list[SeriesPoint]:
    """값마다 누적 지점을 만들되 MAX_POINTS개를 넘으면 고르게 솎는다(마지막 지점은 항상 남긴다).

    비율은 Wilson 구간, 나머지는 정규 근사 구간이다. 표본이 하나면 구간은 그 값 하나다.
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
        low, high = wilson(mean, n) if is_rate else normal(mean, (squares[n] - n * mean * mean), n)
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
