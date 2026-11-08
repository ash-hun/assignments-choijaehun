"""query 기능의 거절 판정(dense 점수 임계값, 근거 부족 토큰) 단위 테스트."""
from app.service.query.prompt_builder import INSUFFICIENT_CONTEXT
from app.service.query.evidence_checker import EvidenceChecker


def test_score_at_or_above_threshold_counts_as_evidence() -> None:
    checker = EvidenceChecker(0.5)

    assert checker.has_evidence(0.5)
    assert not checker.has_evidence(0.4999)
    assert not checker.has_evidence(None)


def test_refusal_token_is_detected_even_with_extra_words() -> None:
    checker = EvidenceChecker(0.5)

    assert checker.is_insufficient(f"Sorry. {INSUFFICIENT_CONTEXT}")
    assert not checker.is_insufficient("uv sync installs the lockfile [1].")
