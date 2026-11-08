"""거절 판정. 검색 단계는 dense 최고 점수 임계값으로, 생성 단계는 모델이 낸 근거 부족 토큰으로 근거 유무를 가른다."""
from app.service.query.prompt_builder import INSUFFICIENT_CONTEXT


class EvidenceChecker:
    """임계값은 dev set으로 보정한 값(research/refusal_threshold.md)을 생성자로 받는다."""

    def __init__(self, threshold: float) -> None:
        self._threshold = threshold

    @property
    def threshold(self) -> float:
        """dense 최고 점수가 이 값 미만이면 LLM을 부르지 않고 거절한다."""
        return self._threshold

    def has_evidence(self, top_dense_score: float | None) -> bool:
        """검색 결과가 없거나 최고 점수가 임계값 미만이면 근거가 없다고 본다."""
        return top_dense_score is not None and top_dense_score >= self._threshold

    def is_insufficient(self, answer: str) -> bool:
        """모델이 근거 부족 토큰을 냈는지. 토큰 앞뒤에 다른 말을 붙여도 근거 부족으로 본다."""
        return INSUFFICIENT_CONTEXT in answer
