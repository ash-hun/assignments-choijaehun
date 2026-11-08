"""selection_run 기능의 거절 임계값 보정(언어별 오거절 상한, 답 없는 문항 최대 거절) 단위 테스트."""
from app.service.eval.refusal_calibrator import TopScore, pick_threshold


def score(language: str, answerable: bool, value: float, n: int) -> TopScore:
    return TopScore(item_id=f"{language}-{answerable}-{n}", language=language, type="factual" if answerable else "unanswerable",
                    answerable=answerable, score=value, doc_id="a.md")


def scores(language: str, answerable: list[float], unanswerable: list[float]) -> list[TopScore]:
    return [score(language, True, v, i) for i, v in enumerate(answerable)] + [score(language, False, v, i) for i, v in enumerate(unanswerable)]


def test_threshold_refuses_most_unanswerable_without_breaking_the_false_refusal_cap() -> None:
    answerable = [0.6 + i * 0.01 for i in range(30)]
    data = scores("en", answerable, [0.3, 0.4, 0.65]) + scores("ko", answerable, [0.35, 0.45])

    verdict = pick_threshold(data)

    assert 0.45 < verdict.chosen.threshold < 0.6
    assert verdict.chosen.false_refusal == {"en": 0.0, "ko": 0.0}
    assert verdict.chosen.unanswerable_refused == {"en": 0.6667, "ko": 1.0}


def test_cap_is_checked_per_language() -> None:
    data = scores("en", [0.3, 0.31] + [0.9] * 28, [0.2]) + scores("ko", [0.9] * 30, [0.5])

    verdict = pick_threshold(data)

    assert verdict.chosen.threshold < 0.31
    assert verdict.chosen.false_refusal["en"] <= 0.05
