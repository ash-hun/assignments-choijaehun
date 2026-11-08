"""ingest 기능의 정제(text_cleaner), 문자 수 고정 분할(FixedLengthSplitter), 토큰 기준 분할(ChunkSplitter) 단위 테스트."""
import re
import pytest
import numpy as np

from app.service.ingest.chunk_splitter import ChunkSplitter, FixedLengthSplitter
from app.service.ingest.text_cleaner import clean_text, extract_title
from app.schema.chunk_schema import Chunk, Document

RAW = """---
title: Caching
---
<!-- hidden -->
<p align="center"><img src="x.png"></p>

# Cache

Run `uv cache clean <name>` to [clean](./cache.md).
"""
WORD = re.compile(r"\S+")


def word_offsets(text: str) -> list[tuple[int, int]]:
    return [m.span() for m in WORD.finditer(text)]


def word_count(text: str) -> int:
    return len(WORD.findall(text)) + 1


def splitter(method: str, max_tokens: int, overlap: int = 0) -> ChunkSplitter:
    return ChunkSplitter(method, max_tokens, overlap, word_count, word_offsets)  # type: ignore[arg-type]


def doc(text: str) -> Document:
    return Document(doc_id="a.md", title="A", text=text)


def test_clean_text_drops_front_matter_comments_and_html_but_keeps_placeholders_and_links() -> None:
    cleaned = clean_text(RAW)

    assert cleaned == "# Cache\n\nRun `uv cache clean <name>` to [clean](./cache.md)."
    assert extract_title(RAW, "a.md") == "Caching"
    assert extract_title("# Only H1\nbody", "b.md") == "Only H1"


def test_split_respects_max_chars_cuts_on_whitespace_and_is_deterministic() -> None:
    splitter_ = FixedLengthSplitter(max_chars=12)

    first = splitter_.split(doc("alpha beta gamma delta epsilon"))

    assert [c.text for c in first] == ["alpha beta", "gamma delta", "epsilon"]
    assert first == splitter_.split(doc("alpha beta gamma delta epsilon"))
    assert first[1].chunk_id == Chunk.make_id("a.md", "gamma delta")


def test_split_force_cuts_a_token_longer_than_max_chars() -> None:
    chunks = FixedLengthSplitter(max_chars=4).split(doc("abcdefghij"))

    assert [c.text for c in chunks] == ["abcd", "efgh", "ij"]


def test_splitter_rejects_overlap_not_smaller_than_size() -> None:
    with pytest.raises(ValueError):
        FixedLengthSplitter(max_chars=10, overlap_chars=10)
    with pytest.raises(ValueError):
        splitter("fixed", 4, 4)
    with pytest.raises(ValueError):
        splitter("semantic", 4)


def test_fixed_fills_to_the_token_budget_and_carries_overlap() -> None:
    chunks = splitter("fixed", 4, 1).split(doc("a b c d e f g"))

    assert [c.text for c in chunks] == ["a b c", "c d e", "e f g"]
    assert all(word_count(c.text) <= 4 for c in chunks)


def test_recursive_cuts_between_paragraphs_where_fixed_cuts_mid_paragraph() -> None:
    text = doc("a b c\n\nd e f\n\ng")

    assert [c.text for c in splitter("recursive", 5).split(text)] == ["a b c", "d e f\n\ng"]
    assert [c.text for c in splitter("fixed", 5).split(text)] == ["a b c\n\nd", "e f\n\ng"]


def test_structure_keeps_sections_whole_and_ignores_hash_lines_in_code() -> None:
    text = "# A\nx y\n## B\n```\n# comment\n```\n## C\np q r s t"
    chunks = splitter("structure", 8).split(doc(text))

    assert [c.text for c in chunks] == ["# A\nx y", "## B\n```\n# comment\n```", "## C\np q r s t"]


def test_text_without_boundaries_is_cut_at_token_positions() -> None:
    by_char = ChunkSplitter("fixed", 4, 0, lambda t: len(t) + 1, lambda t: [(i, i + 1) for i in range(len(t))])

    assert [c.text for c in by_char.split(doc("abcdefg"))] == ["abc", "def", "g"]


def test_sliding_moves_the_window_by_size_minus_overlap() -> None:
    chunks = splitter("sliding", 5, 2).split(doc("a b c d e f g h"))

    assert [c.text for c in chunks] == ["a b c d", "c d e f", "e f g h"]


def topic_vectors(texts: list[str]) -> np.ndarray:
    return np.array([[1.0, 0.0] if t.startswith("a") else [0.0, 1.0] for t in texts])


def test_semantic_cuts_where_neighbouring_sentences_diverge() -> None:
    semantic = ChunkSplitter("semantic", 20, 0, word_count, word_offsets, topic_vectors)

    assert [c.text for c in semantic.split(doc("a1 x. a2 y. b1 z. b2 w."))] == ["a1 x. a2 y.", "b1 z. b2 w."]
