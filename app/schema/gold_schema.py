"""Gold Set 문항 모델. dev set(선정 실험용)과 test set(최종 평가용)이 같은 모델을 쓴다."""
import uuid
from typing import Literal
from pydantic import BaseModel, Field, model_validator

GoldType = Literal["factual", "multi_doc", "summary", "trap", "unanswerable"]
GoldSplit = Literal["dev", "test"]
GoldOrigin = Literal["llm_draft", "llm_draft_reviewed", "human_written"]
GoldLanguage = Literal["en", "ko"]
# 문항 id는 uuid5라 같은 (split, 유형, 순번)이면 다시 만들어도 같은 값이 나온다. 무작위 uuid4는 쓰지 않는다.
GOLD_ID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "elice-rag-qa/gold")


class GoldEvidence(BaseModel):
    """정답 근거 구절. quote는 원문 파일에 글자 그대로 있는 부분 문자열이다."""

    doc_id: str
    quote: str = Field(min_length=1)


class GoldItem(BaseModel):
    """Gold Set 문항 하나."""

    id: uuid.UUID
    split: GoldSplit
    type: GoldType
    question: str = Field(min_length=1, max_length=1000)
    answerable: bool
    reference_answer: str
    evidence: list[GoldEvidence]
    acceptance_criteria: list[str] | None = None
    origin: GoldOrigin
    notes: str | None = None
    # 번역 묶음 행은 원문(영어) 행의 id를 가리킨다. 근거와 정답은 원문 행과 같다.
    language: GoldLanguage = "en"
    translation_of: uuid.UUID | None = None

    @model_validator(mode="after")
    def _evidence_matches_answerability(self) -> "GoldItem":
        if self.answerable != bool(self.evidence):
            raise ValueError("answerable items need evidence and unanswerable items must have none")
        if (self.type == "unanswerable") == self.answerable:
            raise ValueError("type 'unanswerable' must match answerable=false")
        if (self.language != "en") != (self.translation_of is not None):
            raise ValueError("translated items need translation_of and original items must not have it")
        return self

    @staticmethod
    def make_id(split: GoldSplit, type_: GoldType, ordinal: int) -> uuid.UUID:
        """split, 유형, 유형 안 순번에서 결정적으로 id를 만든다."""
        return uuid.uuid5(GOLD_ID_NAMESPACE, f"{split}-{type_}-{ordinal:02d}")

    @staticmethod
    def make_translation_id(source_id: uuid.UUID, language: GoldLanguage) -> uuid.UUID:
        """원문 행 id와 언어에서 번역 행 id를 결정적으로 만든다."""
        return uuid.uuid5(GOLD_ID_NAMESPACE, f"{source_id}:{language}")

    @property
    def gold_doc_ids(self) -> list[str]:
        """근거가 있는 문서 목록. 순서를 유지하고 중복을 뺀다."""
        return list(dict.fromkeys(e.doc_id for e in self.evidence))
