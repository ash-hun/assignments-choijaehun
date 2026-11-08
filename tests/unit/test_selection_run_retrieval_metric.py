"""selection_run 기능의 근거 단위 검색 지표(retrieval_metric)와 bootstrap 구간 단위 테스트."""
import pytest

from app.service.eval.retrieval_metric import score, bootstrap, shares_evidence, evidence_anchors, paired_difference
from app.schema.gold_schema import GoldItem, GoldEvidence
from app.schema.chunk_schema import Chunk

QUOTE = "The cache lock waits five minutes before giving up, which avoids deadlocks between processes."


def chunk(doc_id: str, text: str) -> Chunk:
    return Chunk(chunk_id=Chunk.make_id(doc_id, text), doc_id=doc_id, ordinal=0, text=text)


def item(evidence: list[GoldEvidence], answerable: bool = True) -> GoldItem:
    return GoldItem(
        id=GoldItem.make_id("dev", "factual" if answerable else "unanswerable", 1), split="dev",
        type="factual" if answerable else "unanswerable", question="q", answerable=answerable,
        reference_answer="a" if answerable else "", evidence=evidence, origin="llm_draft_reviewed",
    )


def test_anchors_cover_quote_with_overlapping_windows() -> None:
    anchors = evidence_anchors(QUOTE)

    assert all(len(a) == 60 for a in anchors)
    assert anchors[0] == QUOTE[:60] and anchors[-1] == QUOTE[-60:]
    assert evidence_anchors("short quote") == ["short quote"]


def test_score_counts_a_chunk_holding_part_of_a_split_quote_as_a_hit() -> None:
    gold = item([GoldEvidence(doc_id="cache.md", quote=QUOTE)])
    ranked = [chunk("other.md", QUOTE), chunk("cache.md", "unrelated"), chunk("cache.md", "prefix " + QUOTE[:70])]

    result = score(gold, ranked)

    assert (result.first_hit_rank, result.hit_at_5) == (3, True)
    assert result.reciprocal_rank == pytest.approx(1 / 3)
    assert result.doc_recall_at_5


def test_score_evidence_recall_is_partial_when_one_of_two_quotes_is_missing() -> None:
    gold = item([GoldEvidence(doc_id="a.md", quote=QUOTE), GoldEvidence(doc_id="b.md", quote="Locks are universal and cross-platform for every project.")])

    result = score(gold, [chunk("a.md", QUOTE)])

    assert result.evidence_recall_at_10 == 0.5
    assert result.hit_at_10


def test_score_rejects_unanswerable_items() -> None:
    with pytest.raises(ValueError):
        score(item([], answerable=False), [])


def test_bootstrap_is_deterministic_and_paired_difference_of_equal_lists_is_zero() -> None:
    values = [1.0, 0.0, 1.0, 1.0, 0.0]

    assert bootstrap(values) == bootstrap(values)
    assert bootstrap(values).ci_low <= 0.6 <= bootstrap(values).ci_high
    assert paired_difference(values, values).model_dump() == {"mean": 0.0, "ci_low": 0.0, "ci_high": 0.0}


def test_shares_evidence_detects_a_common_window_in_either_direction() -> None:
    long_quote = "The cache is stored in the user cache directory unless UV_CACHE_DIR is set to another location on disk."

    assert shares_evidence(long_quote, "UV_CACHE_DIR is set to another location on disk.")
    assert shares_evidence("UV_CACHE_DIR is set to another location on disk.", long_quote)
    assert not shares_evidence(long_quote, "Locks are universal across platforms.")
