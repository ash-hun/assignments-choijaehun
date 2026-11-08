"""eval_run 기능의 Judge 지표 계산(judge_metric) 단위 테스트."""
from typing import Any

from app.service.eval.judge_metric import aggregate, parse_rubric, citation_pairs, parse_citations
from app.schema.judge_schema import JudgeResult, RubricJudgment
from app.schema.eval_schema import EvalRecord

RUBRIC: dict[str, Any] = {
    "key_points": [True, True], "rejections": [False], "unsupported_claim": "pass", "identifier_accuracy": "pass",
    "interface_separation": "na", "version_status": "na", "prior_knowledge": "pass", "reason": "",
}


def record(dropped: int = 0) -> EvalRecord:
    return EvalRecord(
        record_id="r:1", run_id="r", source="gold", config_id="c", item_id="1", language="en", type="factual", answerable=True,
        question="q", status="answered", refusal_stage=None, answer="a [1]", cited_chunk_ids=[], dropped_citations=dropped,
        retrieved_chunk_ids=[], retrieval_scores=[0.8], top_score=0.8, rank=None, retrieval_ms=1, first_token_ms=1,
        latency_ms=2, input_tokens=1, output_tokens=2, cost_krw=0.0,
    )


def rubric(sample: int, **overrides: Any) -> JudgeResult:
    return JudgeResult(record_id="r:1", kind="rubric", sample=sample, judge_model="j", prompt_version="v", ok=True,
                       rubric=RubricJudgment(**{**RUBRIC, **overrides}), input_tokens=1, output_tokens=1)


def citation(sample: int, values: list[bool]) -> JudgeResult:
    return JudgeResult(record_id="r:1", kind="citation", sample=sample, judge_model="j", prompt_version="v", ok=True,
                       citations=values, input_tokens=1, output_tokens=1)


def test_citation_pairs_split_sentences_and_skip_code_spans() -> None:
    answer = "Run `uv sync` [1]. It reads `a[2]` and the lockfile [2][3].\n- Cache lives in UV_CACHE_DIR [1]."

    assert citation_pairs(answer) == [
        ("Run `uv sync` [1].", 1), ("It reads `a[2]` and the lockfile [2][3].", 2),
        ("It reads `a[2]` and the lockfile [2][3].", 3), ("- Cache lives in UV_CACHE_DIR [1].", 1),
    ]


def test_parsers_reject_missing_ids_wrong_lengths_and_forbidden_na() -> None:
    assert parse_citations({"judgments": [{"id": 1, "supported": True}, {"id": 0, "supported": False}]}, 2) == [False, True]
    assert parse_citations({"judgments": [{"id": 0, "supported": True}]}, 2) is None
    assert parse_rubric(RUBRIC, 2, 1) is not None
    assert parse_rubric(RUBRIC, 3, 1) is None
    assert parse_rubric({**RUBRIC, "unsupported_claim": "na"}, 2, 1) is None


def test_aggregate_takes_the_majority_and_reports_disagreement() -> None:
    results = [
        rubric(0), rubric(1, key_points=[True, False], prior_knowledge="fail"), rubric(2),
        citation(0, [True, False]), citation(1, [True, False]), citation(2, [True, True]),
    ]

    judged = aggregate(record(dropped=1), results, has_criteria=True)

    assert judged.accuracy is True and judged.key_point_rate == 1.0
    assert judged.citation_precision == 0.5
    assert judged.quality_items["prior_knowledge"] is True and judged.quality_items["interface_separation"] is None
    assert judged.quality_items["no_dropped_citation"] is False
    assert judged.quality_score == 0.75
    assert judged.agreement["accuracy"] is False and judged.agreement["citation_precision"] is False
    assert judged.agreement["unsupported_claim"] is True


def test_aggregate_marks_a_record_without_valid_rubric_samples_as_failed() -> None:
    failed = JudgeResult(record_id="r:1", kind="rubric", sample=0, judge_model="j", prompt_version="v", ok=False,
                         input_tokens=1, output_tokens=1)

    judged = aggregate(record(), [failed], has_criteria=True)

    assert judged.failed and judged.accuracy is None and judged.quality_score is None
