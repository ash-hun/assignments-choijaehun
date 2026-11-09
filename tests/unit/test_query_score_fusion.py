"""query 기능의 검색 융합식(score_fusion) 단위 테스트."""
import pytest

from app.service.query.score_fusion import ordered, min_max, convex_combination, reciprocal_rank_fusion


def test_min_max_scales_to_unit_range_and_equal_scores_become_one() -> None:
    assert min_max([("a", 3.0), ("b", 1.0), ("c", 2.0)]) == {"a": 1.0, "b": 0.0, "c": 0.5}
    assert min_max([("a", 0.7), ("b", 0.7)]) == {"a": 1.0, "b": 1.0}
    assert min_max([]) == {}


def test_convex_combination_weights_normalized_scores_and_treats_missing_as_zero() -> None:
    fused = dict(convex_combination([("a", 0.9), ("b", 0.5)], [("b", 12.0), ("c", 4.0)], alpha=0.5))

    assert fused == {"a": 0.5, "b": 0.5, "c": 0.0}
    with pytest.raises(ValueError):
        convex_combination([("a", 1.0)], [], alpha=1.5)


def test_reciprocal_rank_fusion_sums_reciprocal_ranks_and_ignores_score_size() -> None:
    fused = reciprocal_rank_fusion(["a", "b"], ["b", "c"], k=60)

    assert [cid for cid, _ in fused] == ["b", "a", "c"]
    assert fused[0][1] == pytest.approx(1 / 62 + 1 / 61)
    with pytest.raises(ValueError):
        reciprocal_rank_fusion(["a"], [], k=-1)


def test_ordered_breaks_ties_by_chunk_id() -> None:
    assert ordered({"b": 1.0, "a": 1.0, "c": 2.0}) == [("c", 2.0), ("a", 1.0), ("b", 1.0)]
