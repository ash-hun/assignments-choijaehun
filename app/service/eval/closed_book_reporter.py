"""closed-book 채점 결과를 후보별로 집계한다. 문항 판정은 seed 반복 답변의 다수결로 정한다."""
from pydantic import BaseModel
from collections import Counter

from app.schema.selection_schema import ClosedBookGrade, ClosedBookAnswer

GRADES: tuple[ClosedBookGrade, ...] = ("correct", "partial", "incorrect", "abstain")


class CorpusClosedBookSummary(BaseModel):
    """후보 하나의 closed-book 결과."""

    corpus: str
    questions: int
    answers: int
    answer_grades: dict[str, int]
    question_grades: dict[str, int]
    incorrect_questions: int
    version_incorrect_questions: int
    unanimous_questions: int
    input_tokens: int
    output_tokens: int


def majority_grade(grades: list[ClosedBookGrade]) -> ClosedBookGrade:
    """과반 판정. 과반이 없으면 부분 정답으로 본다. 답이 갈린 문항을 오답으로 세면 Hallucination을 과대 추정한다."""
    top, count = Counter(grades).most_common(1)[0]
    return top if count * 2 > len(grades) else "partial"


def summarize(answers: list[ClosedBookAnswer]) -> list[CorpusClosedBookSummary]:
    """채점된 답변을 후보별로 묶어 요약한다. 채점되지 않은 답변이 있으면 실패한다."""
    if any(a.grade is None for a in answers):
        raise ValueError("ungraded answers present")
    by_corpus: dict[str, list[ClosedBookAnswer]] = {}
    for a in answers:
        by_corpus.setdefault(a.corpus, []).append(a)

    summaries = []
    for corpus, rows in sorted(by_corpus.items()):
        by_question: dict[str, list[ClosedBookAnswer]] = {}
        for a in rows:
            by_question.setdefault(a.id, []).append(a)
        verdicts = {qid: majority_grade([a.grade for a in qs if a.grade]) for qid, qs in by_question.items()}
        categories = {qid: qs[0].category for qid, qs in by_question.items()}
        answer_counts = Counter(a.grade for a in rows)
        question_counts = Counter(verdicts.values())
        summaries.append(
            CorpusClosedBookSummary(
                corpus=corpus,
                questions=len(by_question),
                answers=len(rows),
                answer_grades={g: answer_counts.get(g, 0) for g in GRADES},
                question_grades={g: question_counts.get(g, 0) for g in GRADES},
                incorrect_questions=question_counts.get("incorrect", 0),
                version_incorrect_questions=sum(
                    1 for qid, v in verdicts.items() if v == "incorrect" and categories[qid] == "version_specific"
                ),
                unanimous_questions=sum(1 for qs in by_question.values() if len({a.grade for a in qs}) == 1),
                input_tokens=sum(a.input_tokens for a in rows),
                output_tokens=sum(a.output_tokens for a in rows),
            )
        )
    return summaries
