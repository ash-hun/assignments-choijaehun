"""eval_run 기능의 지표 타당성 판정(validity_checker) 단위 테스트."""
from app.service.eval.validity_variant import strip_citations, shuffle_citations
from app.service.eval.validity_checker import check_variant

METRICS = ["recall_at_5", "correct", "citation_precision", "quality_score", "unsupported_claim", "unanswerable_refused"]


def values(**given: float) -> dict[str, float | None]:
    return {m: given.get(m) for m in METRICS}


def test_variant_passes_only_when_every_expected_metric_drops_beyond_noise() -> None:
    baseline = {str(i): values(citation_precision=1.0) for i in range(10)}
    shuffled = {str(i): values(citation_precision=0.2) for i in range(10)}
    unchanged = {str(i): values(citation_precision=1.0) for i in range(10)}

    passed = check_variant("shuffled_citations", baseline, shuffled)
    failed = check_variant("shuffled_citations", baseline, unchanged)

    assert passed.passed and next(c for c in passed.checks if c.metric == "citation_precision").pairs == 10
    assert not failed.passed
    assert next(c for c in passed.checks if c.metric == "recall_at_5").passed is None


def test_strip_and_shuffle_rewrite_only_citation_markers() -> None:
    assert strip_citations("Use `uv sync` [1][2].") == "Use `uv sync` ."
    assert shuffle_citations("A [1]. B [5].", 5) == "A [2]. B [1]."
