"""eval_run 기능의 순위 기반 검색 지표(rank_score, relevant_chunk_ids) 단위 테스트."""
import math
import pytest

from app.service.eval.retrieval_metric import rank_score, relevant_chunk_ids
from app.schema.gold_schema import GoldItem, GoldEvidence
from app.schema.chunk_schema import Chunk

CACHE = "The cache directory defaults to the user cache folder and can be moved with UV_CACHE_DIR."
LOCK = "The lockfile records exact resolved versions so installs are reproducible across machines."


def chunk(doc: str, text: str, n: int = 0) -> Chunk:
    return Chunk(chunk_id=Chunk.make_id(doc, text), doc_id=doc, ordinal=n, text=text)


def item(evidence: list[GoldEvidence], answerable: bool = True) -> GoldItem:
    return GoldItem(id=GoldItem.make_id("test", "multi_doc" if answerable else "unanswerable", 1), split="test",
                    type="multi_doc" if answerable else "unanswerable", question="q?", answerable=answerable,
                    reference_answer="a" if answerable else "", evidence=evidence, origin="human_written")


def test_rank_score_splits_quote_recall_from_chunk_precision_and_normalizes_dcg() -> None:
    gold = item([GoldEvidence(doc_id="cache.md", quote=CACHE), GoldEvidence(doc_id="lock.md", quote=LOCK)])
    ranked = [chunk("other.md", "unrelated text"), chunk("cache.md", CACHE), chunk("cache.md", "prefix " + CACHE, 1)]
    index = ranked + [chunk("lock.md", LOCK)]

    score = rank_score(gold, ranked, relevant_chunk_ids(gold, index))

    assert relevant_chunk_ids(gold, index) == {c.chunk_id for c in index[1:]}
    assert score.recall_at_5 == 0.5
    assert score.precision_at_5 == 0.4
    assert score.reciprocal_rank == 0.5
    ideal = 1 + 1 / math.log2(3) + 1 / math.log2(4)
    assert score.ndcg_at_10 == round((1 / math.log2(3) + 1 / math.log2(4)) / ideal, 4)


def test_rank_score_rejects_unanswerable_items() -> None:
    with pytest.raises(ValueError):
        rank_score(item([], answerable=False), [], set())
