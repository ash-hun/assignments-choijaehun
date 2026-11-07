"""selection_run 기능의 closed-book 집계(closed_book_reporter) 단위 테스트."""
import pytest

from app.service.eval.closed_book_reporter import majority_grade, summarize
from app.schema.selection_schema import ClosedBookGrade, ClosedBookAnswer


def answer(qid: str, seed: int, grade: ClosedBookGrade | None, category: str = "conceptual") -> ClosedBookAnswer:
    return ClosedBookAnswer.model_validate({
        "id": qid, "corpus": "c", "category": category, "model": "m", "seed": seed,
        "answer": "a", "input_tokens": 1, "output_tokens": 2, "grade": grade,
    })


def test_majority_grade_falls_back_to_partial_without_majority() -> None:
    assert majority_grade(["incorrect", "incorrect", "correct"]) == "incorrect"
    assert majority_grade(["incorrect", "correct", "abstain"]) == "partial"


def test_summarize_counts_question_verdicts_by_majority() -> None:
    rows = [
        answer("q1", 1, "incorrect", "version_specific"), answer("q1", 2, "incorrect", "version_specific"),
        answer("q1", 3, "correct", "version_specific"),
        answer("q2", 1, "correct"), answer("q2", 2, "correct"), answer("q2", 3, "correct"),
    ]

    [summary] = summarize(rows)

    assert summary.incorrect_questions == 1
    assert summary.version_incorrect_questions == 1
    assert summary.unanimous_questions == 1
    assert summary.answer_grades == {"correct": 4, "partial": 0, "incorrect": 2, "abstain": 0}
    assert summary.output_tokens == 12


def test_summarize_rejects_ungraded_answers() -> None:
    with pytest.raises(ValueError, match="ungraded"):
        summarize([answer("q1", 1, None)])
