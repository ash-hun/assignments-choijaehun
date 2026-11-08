"""live_eval 기능의 누적 집계(live_aggregator) 단위 테스트."""
from typing import Any

from app.service.live.live_aggregator import MAX_POINTS, series, wilson, build_snapshot
from app.schema.eval_schema import EvalRecord


def record(n: int, **overrides: Any) -> EvalRecord:
    base: dict[str, Any] = dict(
        record_id=f"live:{n}", run_id=None, source="live", config_id="c", item_id=None, language=None, type=None,
        answerable=None, question="q", status="answered", refusal_stage=None, answer="a [1]", cited_chunk_ids=[],
        dropped_citations=0, retrieved_chunk_ids=[], retrieval_scores=[0.8], top_score=0.8, rank=None, retrieval_ms=10,
        first_token_ms=900, latency_ms=2000, input_tokens=10, output_tokens=5, cost_krw=0.5,
    )
    return EvalRecord(**{**base, **overrides})


def test_series_tracks_cumulative_and_recent_window_with_bounded_wilson_interval() -> None:
    points = series([1.0] * 60 + [0.0] * 40, is_rate=True)

    last = points[-1]
    assert last.n == 100 and last.cum == 0.6
    assert last.window == round(10 / 50, 4)
    assert 0.0 <= last.low < 0.6 < last.high <= 1.0
    assert wilson(1.0, 3)[1] == 1.0 and wilson(0.0, 3)[0] == 0.0


def test_series_thins_long_histories_but_keeps_the_last_point() -> None:
    points = series([float(i) for i in range(1000)], is_rate=False)

    assert len(points) <= MAX_POINTS and points[-1].n == 1000
    assert series([], is_rate=False) == []


def test_snapshot_marks_reference_metrics_and_uses_the_gold_baseline() -> None:
    live = [record(1), record(2, status="insufficient_context", output_tokens=0, top_score=0.6, first_token_ms=None)]
    gold = [record(3, source="gold", run_id="g"), record(4, source="gold", run_id="g")]

    snapshot = build_snapshot("c", live, {}, 0.6375, "g", gold, {}, 12.0, 3000.0, False)

    metrics = {m.key: m for m in snapshot.metrics}
    assert snapshot.records == 2 and snapshot.answered == 1 and snapshot.judged == 0
    assert metrics["refusal_rate"].points[-1].cum == 0.5 and metrics["refusal_rate"].baseline == 0.0
    assert metrics["near_threshold"].points[-1].cum == 0.5
    assert metrics["unsupported_claim"].reference and metrics["unsupported_claim"].points == []
    assert not metrics["latency_ms"].reference and metrics["latency_ms"].points[-1].n == 1
