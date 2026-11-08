"""selection_run 기능의 청크 길이 단위 측정(tokenizer_benchmark) 단위 테스트."""
import pytest

from app.service.eval.tokenizer_benchmark import ratio_stats, measure_units, check_char_limit
from app.schema.chunk_schema import Chunk


def chunk(text: str) -> Chunk:
    return Chunk(chunk_id=Chunk.make_id("a.md", text), doc_id="a.md", ordinal=0, text=text)


def test_measure_units_reports_ratio_to_reference_unit() -> None:
    chunks = [chunk("abcd"), chunk("abcdefgh")]

    units = measure_units(8, chunks, {"chars": len, "half": lambda t: len(t) // 2}, reference="half")

    chars = next(u for u in units if u.unit == "chars")
    assert (chars.max_length, chars.ratio_to_reference.mean, chars.ratio_to_reference.cv) == (8, 2.0, 0.0)


def test_check_char_limit_counts_chunks_over_target_and_cap() -> None:
    chunks = [chunk("x" * 10), chunk("x" * 30)]

    check = check_char_limit(20, "mean_ratio", 30, chunks, len, len, 25)

    assert (check.over_target, check.over_runner_up_cap, check.max_tokens) == (0.5, 0.5, 30)
    assert check.mean_utilization == pytest.approx(1.0)


def test_ratio_stats_single_value_has_zero_spread() -> None:
    stats = ratio_stats([3.0])

    assert (stats.min, stats.p01, stats.max, stats.cv) == (3.0, 3.0, 3.0, 0.0)
