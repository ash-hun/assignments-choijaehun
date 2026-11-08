"""지표 타당성 검증 판정. 같은 문항의 기준선과 망가뜨린 변형을 짝지어, 떨어져야 하는 지표가 실제로 떨어졌는지 본다."""
from pydantic import BaseModel

from app.service.eval.retrieval_metric import MetricSummary, paired_difference
from app.schema.eval_schema import EvalRecord, EvalVariant
from app.schema.judge_schema import RecordJudgment

# research/gold_metric_selection.md의 "지표 타당성 검증" 표. 거절을 끈 변형에서 답 없는 문항은 기준선에서 모두 거절돼
# 품질 점수를 짝지을 수 없어, 거절률만 판정 대상으로 둔다.
EXPECTED_DROPS: dict[str, list[str]] = {
    "random_chunks": ["recall_at_5", "correct"],
    # 무작위 청크를 받은 답변 모델은 대부분 거절해(40문항 중 38) 품질 점수를 짝지을 수 없었다.
    # 실제 답은 그대로 두고 Judge에게만 무작위 청크를 근거로 보여 품질 점수와 인용 판정이 근거를 읽는지 본다.
    "swapped_context": ["quality_score", "citation_precision"],
    "no_refusal": ["unanswerable_refused"],
    "shuffled_citations": ["citation_precision"],
}
METRICS = ["recall_at_5", "correct", "citation_precision", "quality_score", "unanswerable_refused"]


class MetricCheck(BaseModel):
    """지표 하나의 짝지은 차이(기준선 - 변형). expected면 구간 하한이 0보다 커야 통과다."""

    metric: str
    pairs: int
    diff: MetricSummary | None
    expected: bool
    passed: bool | None


class VariantCheck(BaseModel):
    """변형 하나의 판정. 기대한 지표가 모두 떨어졌으면 passed다."""

    variant: str
    checks: list[MetricCheck]
    passed: bool


def item_values(record: EvalRecord, judgment: RecordJudgment | None) -> dict[str, float | None]:
    """문항 하나의 지표 값. 정의되지 않으면 None이라 짝에서 빠진다.

    correct는 답 있는 문항에서 '답했고 정답'이면 1, 거절했거나 오답이면 0이다. 거절도 정답을 못 낸 것으로 센다.
    """
    refused = record.status == "insufficient_context"
    judged = judgment is not None and not judgment.failed
    correct: float | None = None
    if record.answerable:
        if refused:
            correct = 0.0
        elif judged and judgment is not None and judgment.accuracy is not None:
            correct = float(judgment.accuracy)
    return {
        "recall_at_5": record.rank.recall_at_5 if record.rank else None,
        "correct": correct,
        "citation_precision": judgment.citation_precision if judged and judgment is not None else None,
        "quality_score": judgment.quality_score if judged and judgment is not None else None,
        "unanswerable_refused": float(refused) if record.answerable is False else None,
    }


def check_variant(
    variant: EvalVariant, baseline: dict[str, dict[str, float | None]], broken: dict[str, dict[str, float | None]],
) -> VariantCheck:
    """baseline, broken은 item_id별 item_values다. 두 쪽 모두 값이 있는 문항만 짝짓는다."""
    expected = EXPECTED_DROPS.get(variant, [])
    checks = []
    for metric in METRICS:
        shared = sorted(i for i in baseline if i in broken and baseline[i][metric] is not None and broken[i][metric] is not None)
        a = [baseline[i][metric] or 0.0 for i in shared]
        b = [broken[i][metric] or 0.0 for i in shared]
        diff = paired_difference(a, b) if shared else None
        is_expected = metric in expected
        passed = (diff is not None and diff.ci_low > 0) if is_expected else None
        checks.append(MetricCheck(metric=metric, pairs=len(shared), diff=diff, expected=is_expected, passed=passed))
    return VariantCheck(variant=variant, checks=checks, passed=all(c.passed for c in checks if c.expected))
