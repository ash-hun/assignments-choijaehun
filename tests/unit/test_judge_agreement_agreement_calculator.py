"""judge_agreement 기능의 사람 라벨 대비 일치 계산(agreement_calculator) 단위 테스트."""
from typing import Any

from app.schema.judge_schema import HumanLabel, JudgeResult, RubricJudgment
from app.service.eval.agreement_calculator import compare, cohen_kappa

RUBRIC: dict[str, Any] = {"key_points": [True, False], "rejections": [False], "unsupported_claim": "pass",
                          "identifier_accuracy": "fail", "interface_separation": "na", "version_status": "na",
                          "prior_knowledge": "pass", "reason": ""}


def test_kappa_is_one_for_perfect_agreement_and_undefined_for_a_single_category() -> None:
    assert cohen_kappa(["a", "b", "a", "b"], ["a", "b", "a", "b"]) == 1.0
    assert cohen_kappa(["a", "a"], ["a", "a"]) is None
    assert cohen_kappa(["a", "b", "a", "b"], ["b", "a", "b", "a"]) == -1.0


def test_compare_uses_only_complete_labels_and_counts_each_point() -> None:
    judged = {"r1": [JudgeResult(record_id="r1", kind="rubric", sample=s, judge_model="j", prompt_version="v", ok=True,
                                 rubric=RubricJudgment(**RUBRIC), input_tokens=1, output_tokens=1) for s in range(3)]}
    base: dict[str, Any] = dict(item_id="i", language="en", type="factual", citations=[], rejections=[False],
                                unsupported_claim="pass", identifier_accuracy="pass", interface_separation="na",
                                version_status="na", prior_knowledge="pass")
    labels = [HumanLabel(record_id="r1", key_points=[True, True], **base), HumanLabel(record_id="r2", key_points=[None], **base)]

    rows = {r.item: r for r in compare(labels, judged)}

    assert rows["key_point"].pairs == 2 and rows["key_point"].agreement == 0.5
    assert rows["identifier_accuracy"].pairs == 1 and rows["identifier_accuracy"].agreement == 0.0
    assert rows["accuracy"].pairs == 1 and rows["accuracy"].agreement == 0.0
