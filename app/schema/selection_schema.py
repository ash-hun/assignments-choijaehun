"""선정 실험의 입력 문항과 결과 모델."""
from typing import Literal
from pydantic import BaseModel, Field

ClosedBookCategory = Literal["version_specific", "specific_detail", "conceptual"]
ClosedBookGrade = Literal["correct", "partial", "incorrect", "abstain"]


class ClosedBookQuestion(BaseModel):
    """Corpus 원문에서 뽑은 closed-book 검증 문항. evidence는 원문 그대로의 인용이다."""

    id: str
    category: ClosedBookCategory
    question: str = Field(min_length=1, max_length=1000)
    reference_answer: str
    source_path: str
    evidence: str


class ClosedBookAnswer(BaseModel):
    """근거 없이 받은 모델 답변. grade는 채점 후 채운다."""

    id: str
    corpus: str
    category: ClosedBookCategory
    model: str
    seed: int
    answer: str
    input_tokens: int
    output_tokens: int
    grade: ClosedBookGrade | None = None
