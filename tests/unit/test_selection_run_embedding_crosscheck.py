"""selection_run 기능의 Embedding 교차 확인 판정(Hit@5 차이, 근거 보존@5, 비용 규칙) 단위 테스트."""
from app.service.eval.retrieval_metric import RetrievalScore, summarize
from app.service.eval.embedding_crosscheck import ModelResult, judge
from app.service.eval.chunking_benchmark import ChunkingRun


def result(model: str, hits: list[bool], coverage: float) -> ModelResult:
    scores = [
        RetrievalScore(item_id=str(i), type="factual", first_hit_rank=1 if h else None, hit_at_5=h, hit_at_10=h,
                       evidence_recall_at_10=float(h), doc_recall_at_5=h, reciprocal_rank=float(h))
        for i, h in enumerate(hits)
    ]
    runs = [
        ChunkingRun(config="structure-512-77", language=language, **summarize(scores).model_dump(), chunks=1, mean_tokens=1.0,
                    max_tokens=1, evidence_preserved=1.0, quotes_preserved=1.0, context_tokens_mean=1.0,
                    evidence_covered_at_5=coverage, evidence_covered_at_10=coverage, split_seconds=0.0, index_seconds=0.0,
                    per_question=scores)
        for language in ("en", "ko")
    ]
    return ModelResult(model=model, max_input_tokens=512, truncated_chunks=0, runs=runs)


def test_tied_hit_rate_picks_the_cheaper_challenger_when_its_coverage_is_not_lower() -> None:
    same = [True] * 27 + [False] * 3

    verdict = judge(result("qwen", same, 0.8), result("e5", same, 0.8))

    assert (verdict.chosen, verdict.reason) == ("e5", "tied_challenger_cheaper")


def test_tied_hit_rate_keeps_the_incumbent_when_challenger_coverage_is_lower() -> None:
    same = [True] * 27 + [False] * 3

    verdict = judge(result("qwen", same, 0.8), result("e5", same, 0.7))

    assert (verdict.chosen, verdict.reason) == ("qwen", "tied_challenger_coverage_lower")


def test_clearly_better_hit_rate_wins_regardless_of_coverage() -> None:
    verdict = judge(result("qwen", [True] * 10 + [False] * 20, 1.0), result("e5", [True] * 30, 0.1))

    assert (verdict.chosen, verdict.reason) == ("e5", "challenger_better")
    assert all(d.ci_high < 0 for d in verdict.hit_at_5_diff.values())
