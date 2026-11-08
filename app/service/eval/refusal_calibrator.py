"""거절 임계값 보정. dev set 문항별 dense 최고 점수로, 답 있는 문항의 오거절 상한 안에서 답 없는 문항을 가장 많이 거르는 값을 고른다."""
import statistics
from pydantic import BaseModel

# 계획서의 상한. 언어마다 따로 지켜야 한다(한 언어의 오거절을 다른 언어가 덮지 않게).
MAX_FALSE_REFUSAL = 0.05


class TopScore(BaseModel):
    """문항 하나의 dense 최고 점수와 그 청크의 문서."""

    item_id: str
    language: str
    type: str
    answerable: bool
    score: float
    doc_id: str


class ThresholdPoint(BaseModel):
    """임계값 후보 하나. 점수가 threshold 미만이면 거절한다."""

    threshold: float
    false_refusal: dict[str, float]
    unanswerable_refused: dict[str, float]


class ThresholdVerdict(BaseModel):
    """고른 임계값과 모든 후보의 곡선."""

    max_false_refusal: float
    chosen: ThresholdPoint
    curve: list[ThresholdPoint]


def pick_threshold(scores: list[TopScore], max_false_refusal: float = MAX_FALSE_REFUSAL) -> ThresholdVerdict:
    """후보는 0과 관측 점수 사이의 중간값들이다. 모든 언어에서 오거절이 상한 이하인 후보 중 답 없는 문항을 가장 많이 거르는 값,
    같으면 낮은 값(오거절 위험이 작은 쪽)을 고른다.
    """
    distinct = sorted({s.score for s in scores})
    candidates = [0.0] + [(a + b) / 2 for a, b in zip(distinct, distinct[1:])] + ([distinct[-1] + 1e-6] if distinct else [])
    languages = sorted({s.language for s in scores})
    curve = [_point(t, scores, languages) for t in candidates]
    allowed = [p for p in curve if all(v <= max_false_refusal for v in p.false_refusal.values())]
    chosen = max(allowed, key=lambda p: (sum(p.unanswerable_refused.values()), -p.threshold))
    return ThresholdVerdict(max_false_refusal=max_false_refusal, chosen=chosen, curve=curve)


def _point(threshold: float, scores: list[TopScore], languages: list[str]) -> ThresholdPoint:
    def refused(answerable: bool, language: str) -> float:
        group = [s.score < threshold for s in scores if s.answerable == answerable and s.language == language]
        return round(statistics.fmean(group), 4) if group else 0.0

    return ThresholdPoint(
        threshold=threshold,
        false_refusal={lang: refused(True, lang) for lang in languages},
        unanswerable_refused={lang: refused(False, lang) for lang in languages},
    )
