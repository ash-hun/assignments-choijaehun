"""ingest 기능의 정제(text_cleaner)와 고정 길이 분할(FixedLengthSplitter) 단위 테스트."""
import pytest

from app.service.ingest.text_cleaner import clean_text, extract_title
from app.service.ingest.chunk_splitter import FixedLengthSplitter
from app.schema.chunk_schema import Chunk, Document

RAW = """---
title: Caching
---
<!-- hidden -->
<p align="center"><img src="x.png"></p>

# Cache

Run `uv cache clean <name>` to [clean](./cache.md).
"""


def test_clean_text_drops_front_matter_comments_and_html_but_keeps_placeholders_and_links() -> None:
    cleaned = clean_text(RAW)

    assert cleaned == "# Cache\n\nRun `uv cache clean <name>` to [clean](./cache.md)."
    assert extract_title(RAW, "a.md") == "Caching"
    assert extract_title("# Only H1\nbody", "b.md") == "Only H1"


def test_split_respects_max_chars_cuts_on_whitespace_and_is_deterministic() -> None:
    doc = Document(doc_id="a.md", title="A", text="alpha beta gamma delta epsilon")
    splitter = FixedLengthSplitter(max_chars=12)

    first = splitter.split(doc)

    assert [c.text for c in first] == ["alpha beta", "gamma delta", "epsilon"]
    assert all(len(c.text) <= 12 for c in first)
    assert first == splitter.split(doc)
    assert first[1].chunk_id == Chunk.make_id("a.md", "gamma delta")


def test_split_force_cuts_a_token_longer_than_max_chars() -> None:
    chunks = FixedLengthSplitter(max_chars=4).split(Document(doc_id="a.md", title="A", text="abcdefghij"))

    assert [c.text for c in chunks] == ["abcd", "efgh", "ij"]


def test_splitter_rejects_overlap_not_smaller_than_size() -> None:
    with pytest.raises(ValueError):
        FixedLengthSplitter(max_chars=10, overlap_chars=10)
