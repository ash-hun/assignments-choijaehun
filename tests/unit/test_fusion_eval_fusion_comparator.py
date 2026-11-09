"""fusion_eval 기능의 조건 비교(fusion_comparator) 단위 테스트."""
import pytest
from typing import Any

from app.service.eval.fusion_comparator import ItemValues, verdict, paired_diff, group_means, paired_interval


def item(n: int, language: str, value: float | None, type_: str = "factual") -> ItemValues:
    values: dict[str, Any] = {"recall_at_5": value}
    return ItemValues(key=(f"q{n}", language), type=type_, values=values)


def test_paired_diff_pairs_only_items_present_in_both_and_counts_direction() -> None:
    a = [item(1, "en", 1.0), item(2, "en", 0.5), item(3, "en", None), item(4, "ko", 1.0)]
    b = [item(1, "en", 0.5), item(2, "en", 1.0), item(3, "en", 1.0)]

    diff = paired_diff("rrf", a, "dense", b, "recall_at_5", 0.9875)

    assert diff.pairs == 2 and diff.mean == 0.0
    assert (diff.improved, diff.worsened) == (1, 1)
    assert diff.verdict == "inconclusive"
    assert paired_diff("rrf", [], "dense", b, "recall_at_5", 0.9875).verdict is None


def test_verdict_and_interval_follow_the_preregistered_rule() -> None:
    assert verdict(0.01, 0.2) == "supported"
    assert verdict(-0.2, -0.01) == "rejected"
    assert verdict(-0.1, 0.1) == "inconclusive"
    mean, low, high = paired_interval([0.5] * 10, 0.9875)
    assert (mean, low, high) == (0.5, 0.5, 0.5)
    with pytest.raises(ValueError):
        paired_interval([0.1], 1.0)


def test_group_means_split_by_language_and_type() -> None:
    items = [item(1, "en", 1.0, "trap"), item(2, "en", 0.0, "factual"), item(3, "ko", 0.5, "trap")]

    means = {g.group: (g.n, g.mean) for g in group_means("cc", items, "recall_at_5")}

    assert means["all"] == (3, 0.5)
    assert means["en"] == (2, 0.5) and means["en/trap"] == (1, 1.0) and means["ko/trap"] == (1, 0.5)
