"""검색 방식 비교(Part C). 같은 문항끼리 짝지은 차이의 보정 bootstrap 구간으로 판정하고, 언어와 유형별 평균을 낸다."""
import random
import statistics
from typing import Literal
from pydantic import BaseModel

from app.service.eval.retrieval_metric import BOOTSTRAP_SEED, BOOTSTRAP_SAMPLES
from app.schema.judge_schema import RecordJudgment
from app.schema.eval_schema import EvalRecord

Verdict = Literal["supported", "rejected", "inconclusive"]
ItemKey = tuple[str, str]
METRICS = ["recall_at_5", "ndcg_at_10", "mrr_at_10", "precision_at_5", "accuracy", "answerable_refused", "unanswerable_refused"]


class ItemValues(BaseModel):
    """문항 하나(item_id, language)의 지표 값. None은 정의되지 않아 짝에서 빠진다."""

    key: ItemKey
    type: str
    values: dict[str, float | None]


class PairedDiff(BaseModel):
    """두 조건의 같은 문항 차이(a − b). level은 구간 수준(Bonferroni 보정 후)이다."""

    metric: str
    a: str
    b: str
    pairs: int
    mean: float | None
    ci_low: float | None
    ci_high: float | None
    level: float
    verdict: Verdict | None
    improved: int
    worsened: int


class GroupMean(BaseModel):
    """조건 하나의 부분집합 평균. 문항이 적어 구간 대신 방향만 읽는다."""

    condition: str
    group: str
    metric: str
    n: int
    mean: float | None


def item_values(record: EvalRecord, judgment: RecordJudgment | None) -> ItemValues:
    """accuracy는 답했고 판정이 있는 문항에서만 정의된다(답한 문항 중 정답 비율, 11단계와 같은 정의)."""
    judged = judgment is not None and not judgment.failed and judgment.accuracy is not None
    answered = record.status == "answered"
    rank = record.rank
    return ItemValues(key=(record.item_id or record.record_id, record.language or ""), type=record.type or "", values={
        "recall_at_5": rank.recall_at_5 if rank else None,
        "ndcg_at_10": rank.ndcg_at_10 if rank else None,
        "mrr_at_10": rank.reciprocal_rank if rank else None,
        "precision_at_5": rank.precision_at_5 if rank else None,
        "accuracy": float(judgment.accuracy) if answered and judged and judgment is not None and judgment.accuracy is not None else None,
        "answerable_refused": float(not answered) if record.answerable else None,
        "unanswerable_refused": float(not answered) if record.answerable is False else None,
    })


def paired_interval(diffs: list[float], level: float) -> tuple[float, float, float]:
    """평균과 양쪽 (1 − level)/2 분위 구간. seed가 고정이라 같은 입력이면 같은 구간이다."""
    if not 0.0 < level < 1.0:
        raise ValueError(f"level must be in (0, 1), got {level}")
    rng = random.Random(BOOTSTRAP_SEED)
    means = sorted(statistics.fmean(rng.choices(diffs, k=len(diffs))) for _ in range(BOOTSTRAP_SAMPLES))
    tail = (1.0 - level) / 2
    low = means[int(tail * BOOTSTRAP_SAMPLES)]
    high = means[min(BOOTSTRAP_SAMPLES - 1, int((1.0 - tail) * BOOTSTRAP_SAMPLES) - 1)]
    return round(statistics.fmean(diffs), 4), round(low, 4), round(high, 4)


def verdict(low: float, high: float) -> Verdict:
    """구간 하한이 0보다 크면 지지, 상한이 0보다 작으면 기각, 0을 포함하면 판정 불가."""
    if low > 0:
        return "supported"
    if high < 0:
        return "rejected"
    return "inconclusive"


def paired_diff(a_name: str, a: list[ItemValues], b_name: str, b: list[ItemValues], metric: str, level: float) -> PairedDiff:
    """두 조건 모두 값이 있는 문항만 짝짓는다."""
    b_by_key = {item.key: item.values.get(metric) for item in b}
    pairs = [(x, y) for item in a if (x := item.values.get(metric)) is not None and (y := b_by_key.get(item.key)) is not None]
    diffs = [x - y for x, y in pairs]
    if not diffs:
        return PairedDiff(metric=metric, a=a_name, b=b_name, pairs=0, mean=None, ci_low=None, ci_high=None, level=level,
                          verdict=None, improved=0, worsened=0)
    mean, low, high = paired_interval(diffs, level)
    return PairedDiff(metric=metric, a=a_name, b=b_name, pairs=len(diffs), mean=mean, ci_low=low, ci_high=high, level=level,
                      verdict=verdict(low, high), improved=sum(d > 0 for d in diffs), worsened=sum(d < 0 for d in diffs))


def group_means(condition: str, items: list[ItemValues], metric: str) -> list[GroupMean]:
    """전체, 언어별, 언어와 유형별 평균."""
    groups: dict[str, list[float]] = {}
    for item in items:
        value = item.values.get(metric)
        if value is None:
            continue
        language = item.key[1]
        for group in ("all", language, f"{language}/{item.type}"):
            groups.setdefault(group, []).append(value)
    return [GroupMean(condition=condition, group=g, metric=metric, n=len(v), mean=round(statistics.fmean(v), 4))
            for g, v in sorted(groups.items())]


def retrieval_refusals(records: list[EvalRecord]) -> set[ItemKey]:
    """검색 단계에서 거절한 문항. 거절 판정이 검색 방식과 무관하면 모든 조건에서 같아야 한다."""
    return {(r.item_id or r.record_id, r.language or "") for r in records if r.refusal_stage == "retrieval"}
