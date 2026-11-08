"""selection_run 기능의 Chunking 판정(근거 보존율, 사전 규칙에 따른 설정 선택) 단위 테스트."""
from app.service.eval.chunking_benchmark import ChunkingRun, pick_best, evidence_covered, evidence_preservation
from app.service.eval.retrieval_metric import RetrievalScore, summarize
from app.schema.gold_schema import GoldItem, GoldEvidence
from app.schema.chunk_schema import Chunk

QUOTE = "The cache lock waits five minutes."


def chunk(doc_id: str, text: str) -> Chunk:
    return Chunk(chunk_id=Chunk.make_id(doc_id, text), doc_id=doc_id, ordinal=0, text=text)


def item(ordinal: int, quotes: list[str]) -> GoldItem:
    return GoldItem(
        id=GoldItem.make_id("dev", "factual", ordinal), split="dev", type="factual", question="q", answerable=True,
        reference_answer="a", evidence=[GoldEvidence(doc_id="cache.md", quote=q) for q in quotes], origin="llm_draft_reviewed",
    )


def run(config: str, hits: list[bool], preserved: float, context: float) -> list[ChunkingRun]:
    scores = [
        RetrievalScore(item_id=str(i), type="factual", first_hit_rank=1 if h else None, hit_at_5=h, hit_at_10=h,
                       evidence_recall_at_10=float(h), doc_recall_at_5=h, reciprocal_rank=float(h))
        for i, h in enumerate(hits)
    ]
    return [
        ChunkingRun(config=config, language=language, **summarize(scores).model_dump(), chunks=1, mean_tokens=1.0, max_tokens=1,
                    evidence_preserved=preserved, quotes_preserved=preserved, context_tokens_mean=context, evidence_covered_at_5=1.0, evidence_covered_at_10=1.0, split_seconds=0.0, index_seconds=0.0,
                    per_question=scores)
        for language in ("en", "ko")
    ]


def test_preservation_needs_every_quote_whole_inside_one_chunk_of_the_same_doc() -> None:
    items = [item(1, [QUOTE]), item(2, [QUOTE, "Second quote here."])]
    chunks = [chunk("cache.md", "Intro. The cache lock\nwaits five minutes. Second"), chunk("other.md", "Second quote here.")]

    assert evidence_preservation(items, chunks) == (0.5, 0.6667)


def test_pick_best_breaks_hit_ties_by_preservation_then_context_tokens() -> None:
    same = [True] * 9 + [False]
    runs = run("small", same, 0.8, 900.0) + run("large", same, 0.9, 2000.0) + run("lean", same, 0.9, 1500.0)

    verdict = pick_best(runs)

    assert verdict.chosen == "lean"
    assert all(r.tied for r in verdict.rows)


def test_pick_best_drops_a_config_clearly_worse_on_hit_at_5() -> None:
    runs = run("good", [True] * 30, 0.5, 900.0) + run("bad", [True] * 10 + [False] * 20, 1.0, 100.0)

    verdict = pick_best(runs)

    assert (verdict.leader, verdict.chosen) == ("good", "good")
    assert [r.tied for r in verdict.rows] == [True, False]


def test_coverage_counts_a_quote_split_across_two_retrieved_chunks() -> None:
    quote = "The cache lock waits five minutes before giving up, which avoids deadlocks between processes in practice."
    gold = item(1, [quote])
    halves = [chunk("cache.md", quote[:60]), chunk("other.md", "noise"), chunk("cache.md", quote[45:])]

    assert evidence_covered(gold, halves, 3)
    assert not evidence_covered(gold, halves, 2)
