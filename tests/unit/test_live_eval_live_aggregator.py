"""live_eval 기능의 누적 집계(live_aggregator) 단위 테스트."""
from typing import Any
from datetime import datetime, timedelta

from app.service.live.live_aggregator import RECENT, MAX_POINTS, SeriesPoint, series, wilson, verdict, build_snapshot
from app.schema.eval_schema import EvalRecord, LiveRecord
from app.schema.judge_schema import RecordJudgment


def record(n: int, **overrides: Any) -> EvalRecord:
    base: dict[str, Any] = dict(
        record_id=f"live:{n}", run_id=None, source="live", config_id="c", item_id=None, language=None, type=None,
        answerable=None, question="q", status="answered", refusal_stage=None, answer="a [1]", cited_chunk_ids=[],
        dropped_citations=0, retrieved_chunk_ids=[], retrieval_scores=[0.8], top_score=0.8, rank=None, retrieval_ms=10,
        first_token_ms=900, latency_ms=2000, input_tokens=10, output_tokens=5, cost_krw=0.5,
    )
    return EvalRecord(**{**base, **overrides})


def live(*records: EvalRecord) -> list[LiveRecord]:
    return [LiveRecord(record=r, recorded_at=datetime(2026, 1, 1) + timedelta(seconds=i)) for i, r in enumerate(records)]


def point(n: int, low: float, high: float) -> SeriesPoint:
    return SeriesPoint(n=n, cum=(low + high) / 2, low=low, high=high, window=0.0)


def test_series_tracks_cumulative_and_recent_window_with_bounded_wilson_interval() -> None:
    points = series([1.0] * 60 + [0.0] * 40, "rate")

    last = points[-1]
    assert last.n == 100 and last.cum == 0.6
    assert last.window == round(10 / 50, 4)
    assert 0.0 <= last.low < 0.6 < last.high <= 1.0
    assert wilson(1.0, 3)[1] == 1.0 and wilson(0.0, 3)[0] == 0.0


def test_series_thins_long_histories_but_keeps_the_last_point() -> None:
    points = series([float(i) for i in range(1000)], "ms")

    assert len(points) <= MAX_POINTS and points[-1].n == 1000
    assert series([], "ms") == []


def test_snapshot_marks_reference_metrics_and_uses_the_gold_baseline() -> None:
    rows = live(record(1), record(2, status="insufficient_context", refusal_stage="retrieval", output_tokens=0, top_score=0.6,
                                 first_token_ms=None), record(3, status="insufficient_context", refusal_stage="generation"))
    gold = [record(3, source="gold", run_id="g"), record(4, source="gold", run_id="g")]

    snapshot = build_snapshot("c", rows, {}, 0.6375, "g", gold, {}, 12.0, 3000.0, False, 1.0)

    metrics = {m.key: m for m in snapshot.metrics}
    assert snapshot.records == 3 and snapshot.answered == 1 and snapshot.judged == 0
    assert metrics["refusal_retrieval"].group == "retrieval" and metrics["refusal_retrieval"].points[-1].cum == round(1 / 3, 4)
    assert metrics["refusal_generation"].points[-1].n == 2 and metrics["refusal_generation"].points[-1].cum == 0.5
    assert metrics["refusal_retrieval"].baseline == 0.0 and metrics["cost_krw"].group == "ops"
    assert metrics["near_threshold"].points[-1].cum == round(1 / 3, 4)
    assert metrics["unsupported_claim"].reference and metrics["unsupported_claim"].points == []
    assert not metrics["latency_ms"].reference and metrics["latency_ms"].points[-1].n == 1
    assert metrics["refusal_retrieval"].verdict == "few" and metrics["unsupported_claim"].verdict is None


def test_score_interval_stays_within_zero_and_one() -> None:
    last = series([1.0, 0.0, 1.0], "score")[-1]

    assert 0.0 <= last.low and last.high == 1.0
    assert series([1.0, 0.0, 1.0], "ms")[-1].high > 1.0


def test_verdict_compares_the_baseline_with_the_cumulative_interval_once_enough_samples_exist() -> None:
    assert verdict(point(10, 0.2, 0.4), 0.3) == "within"
    assert verdict(point(10, 0.2, 0.4), 0.1) == "above"
    assert verdict(point(10, 0.2, 0.4), 0.5) == "below"
    assert verdict(point(9, 0.2, 0.4), 0.9) == "few"
    assert verdict(None, 0.3) is None and verdict(point(10, 0.2, 0.4), None) is None


def test_recent_lists_newest_first_with_judge_state_and_no_question_text() -> None:
    judged = RecordJudgment(record_id="live:1", samples=1, citation_precision=0.5, accuracy=None, key_point_rate=None,
                            quality_items={"unsupported_claim": True}, quality_score=None, agreement={}, failed=False)
    last = RECENT + 5
    rows = live(*(record(i) for i in range(1, last)), record(last, status="insufficient_context", refusal_stage="retrieval"))

    recent = build_snapshot("c", rows, {"live:1": judged}, 0.6, None, [], {}, 0.0, 10.0, False, 1.0).recent
    exhausted = build_snapshot("c", rows, {}, 0.6, None, [], {}, 10.0, 10.0, True, 1.0).recent

    assert len(recent) == RECENT and recent[0].request_id == str(last) and recent[-1].request_id == "6"
    assert recent[0].judge == "skipped" and recent[0].refusal_stage == "retrieval"
    assert recent[1].judge == "pending" and exhausted[1].judge == "skipped"
    assert "question" not in recent[0].model_dump()
    first = build_snapshot("c", live(record(1)), {"live:1": judged}, 0.6, None, [], {}, 0.0, 10.0, False, 1.0).recent[0]
    assert first.judge == "judged" and first.unsupported_claim is True and first.citation_precision == 0.5
