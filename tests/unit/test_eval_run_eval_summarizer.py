"""eval_run 기능의 기록 요약(eval_summarizer)과 run_id 계산 단위 테스트."""
from typing import Any

from app.schema.eval_schema import RankScore, EvalConfig, EvalRecord, EvalManifest
from app.service.eval.eval_summarizer import tpot_ms, summarize_records

RANK = RankScore(recall_at_5=1.0, recall_at_10=1.0, precision_at_5=0.2, precision_at_10=0.1, f1_at_5=0.3333,
                 f1_at_10=0.1818, reciprocal_rank=1.0, ndcg_at_10=1.0)


def record(n: int, **overrides: Any) -> EvalRecord:
    base: dict[str, Any] = dict(
        record_id=f"r:{n}", run_id="r", source="gold", config_id="c", item_id=str(n), language="en", type="factual",
        answerable=True, question="q", status="answered", refusal_stage=None, answer="a [1]", cited_chunk_ids=["x"],
        dropped_citations=0, retrieved_chunk_ids=["x"], retrieval_scores=[0.8], top_score=0.8, rank=RANK,
        retrieval_ms=40, first_token_ms=1000, latency_ms=2000, input_tokens=1000, output_tokens=101, cost_krw=0.2,
    )
    return EvalRecord(**{**base, **overrides})


def test_summary_counts_refusals_by_answerability_and_stage() -> None:
    records = [
        record(1),
        record(2, answerable=False, type="unanswerable", rank=None, status="insufficient_context", refusal_stage="retrieval",
               top_score=0.6, first_token_ms=None, output_tokens=0, input_tokens=0, cost_krw=0.0),
        record(3, status="insufficient_context", refusal_stage="generation", first_token_ms=None, top_score=0.65),
    ]

    [summary] = summarize_records(records, threshold=0.6375)

    assert summary.unanswerable_refusal is not None and summary.unanswerable_refusal.mean == 1.0
    assert summary.answerable_false_refusal is not None and summary.answerable_false_refusal.mean == 0.5
    assert summary.refusals_by_stage == {"generation": 1, "retrieval": 1}
    assert summary.near_threshold_rate == round(2 / 3, 4)
    assert summary.tpot_ms.median == 10.0
    assert summary.ttft_ms.count == 1


def test_tpot_is_undefined_for_refusals_and_single_token_answers() -> None:
    assert tpot_ms(record(1, status="insufficient_context", first_token_ms=None)) is None
    assert tpot_ms(record(1, output_tokens=1)) is None


def test_run_id_ignores_git_commit_but_follows_config() -> None:
    def manifest(name: str, commit: str) -> EvalManifest:
        return EvalManifest(
            config=EvalConfig(name=name, gold_files=["g.jsonl"]), config_id="c", gold_hashes={"g.jsonl": "h"},
            corpus_manifest_hash="m", index_contract={"embedding_model": "e"}, collection="col", answer_model="a",
            answer_temperature=0.0, answer_seed=None, answer_max_tokens=10, refusal_threshold=0.6, prompt_hash="p",
            bootstrap_seed=1, git_commit=commit,
        )

    assert manifest("base", "abc").run_id() == manifest("base", "def").run_id()
    assert manifest("base", "abc").run_id() != manifest("hybrid", "abc").run_id()
    assert manifest("base", "abc").run_id().startswith("base-")
