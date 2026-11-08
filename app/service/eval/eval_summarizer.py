"""평가 기록을 언어별 지표 요약으로 묶는다. 비율과 평균에는 문항 bootstrap 95% 구간을 붙이고, 지연은 중앙값과 p95를 낸다."""
import statistics
from pydantic import BaseModel

from app.service.eval.retrieval_metric import MetricSummary, bootstrap
from app.schema.eval_schema import EvalRecord

RANK_FIELDS = ["recall_at_5", "recall_at_10", "precision_at_5", "precision_at_10", "f1_at_5", "f1_at_10",
               "reciprocal_rank", "ndcg_at_10"]
# 거절 임계값 근처에 몰린 질의는 판정이 흔들린다(research/gold_metric_selection.md).
NEAR_THRESHOLD = 0.05


class LatencySummary(BaseModel):
    """밀리초 단위 중앙값과 p95. 값이 없으면 둘 다 None이다."""

    count: int
    median: float | None
    p95: float | None


class LanguageSummary(BaseModel):
    """언어 하나의 지표. 검색 지표는 답 있는 문항, 거절 지표는 해당 문항, 운영 지표는 전체 문항으로 잰다."""

    language: str
    items: int
    retrieval: dict[str, MetricSummary]
    retrieval_by_type: dict[str, dict[str, float]]
    top_score_median: float | None
    near_threshold_rate: float
    unanswerable_refusal: MetricSummary | None
    answerable_false_refusal: MetricSummary | None
    refusals_by_stage: dict[str, int]
    no_dropped_citation_rate: MetricSummary | None
    retrieval_ms: LatencySummary
    ttft_ms: LatencySummary
    tpot_ms: LatencySummary
    latency_ms: LatencySummary
    refused_latency_ms: LatencySummary
    cost_krw_per_item: float
    cost_krw_total: float


def summarize_records(records: list[EvalRecord], threshold: float) -> list[LanguageSummary]:
    """언어 이름 순으로 요약한다. 같은 기록이면 같은 요약이 나온다."""
    return [_language(language, [r for r in records if (r.language or "unknown") == language], threshold)
            for language in sorted({r.language or "unknown" for r in records})]


def tpot_ms(record: EvalRecord) -> float | None:
    """(Latency - TTFT) / (출력 토큰 - 1). 첫 토큰을 흘리지 않은 답(검색, 생성 단계 거절)이나 토큰이 1개 이하면 None."""
    if record.first_token_ms is None or record.output_tokens <= 1 or record.status != "answered":
        return None
    return (record.latency_ms - record.first_token_ms) / (record.output_tokens - 1)


def _language(language: str, group: list[EvalRecord], threshold: float) -> LanguageSummary:
    ranked = [(r.type or "unknown", r.rank) for r in group if r.rank is not None]
    by_type: dict[str, dict[str, list[float]]] = {}
    for item_type, rank in ranked:
        for name in ("recall_at_5", "ndcg_at_10"):
            by_type.setdefault(item_type, {}).setdefault(name, []).append(getattr(rank, name))
    tops = [r.top_score for r in group if r.top_score is not None]
    answerable = [r for r in group if r.answerable]
    unanswerable = [r for r in group if r.answerable is False]
    answered = [r for r in group if r.status == "answered"]
    refused = [r for r in group if r.status == "insufficient_context"]
    stages: dict[str, int] = {}
    for r in refused:
        stages[r.refusal_stage or "unknown"] = stages.get(r.refusal_stage or "unknown", 0) + 1
    costs = [r.cost_krw for r in group]
    return LanguageSummary(
        language=language,
        items=len(group),
        retrieval={name: bootstrap([getattr(rank, name) for _, rank in ranked]) for name in RANK_FIELDS} if ranked else {},
        retrieval_by_type={t: {n: round(statistics.fmean(v), 4) for n, v in m.items()} for t, m in sorted(by_type.items())},
        top_score_median=round(statistics.median(tops), 4) if tops else None,
        near_threshold_rate=round(sum(abs(t - threshold) <= NEAR_THRESHOLD for t in tops) / len(tops), 4) if tops else 0.0,
        unanswerable_refusal=_rate([r.status == "insufficient_context" for r in unanswerable]),
        answerable_false_refusal=_rate([r.status == "insufficient_context" for r in answerable]),
        refusals_by_stage=dict(sorted(stages.items())),
        no_dropped_citation_rate=_rate([r.dropped_citations == 0 for r in answered]),
        retrieval_ms=_latency([r.retrieval_ms for r in group]),
        ttft_ms=_latency([r.first_token_ms for r in answered]),
        tpot_ms=_latency([tpot_ms(r) for r in answered]),
        latency_ms=_latency([float(r.latency_ms) for r in answered]),
        refused_latency_ms=_latency([float(r.latency_ms) for r in refused]),
        cost_krw_per_item=round(statistics.fmean(costs), 4) if costs else 0.0,
        cost_krw_total=round(sum(costs), 4),
    )


def _rate(flags: list[bool]) -> MetricSummary | None:
    return bootstrap([float(f) for f in flags]) if flags else None


def _latency(values: list[float | int | None]) -> LatencySummary:
    present = sorted(float(v) for v in values if v is not None)
    if not present:
        return LatencySummary(count=0, median=None, p95=None)
    p95 = present[min(len(present) - 1, int(0.95 * len(present)))]
    return LatencySummary(count=len(present), median=round(statistics.median(present), 1), p95=round(p95, 1))
