"""ingest 기능의 BM25 단어 토큰화(text_tokenizer) 단위 테스트."""
import pytest

from app.common.text_tokenizer import TextTokenizer

TEXT = "Run `uv sync --frozen` to install from uv.lock이 Locked"


def test_whitespace_split_strips_edge_punctuation_only() -> None:
    assert TextTokenizer("whitespace").tokenize(TEXT) == ["run", "uv", "sync", "--frozen", "to", "install", "from", "uv.lock이", "locked"]


def test_word_split_separates_hangul_particles_and_stems_english() -> None:
    tokens = TextTokenizer("word", stem=True).tokenize(TEXT)

    assert tokens[-3:] == ["lock", "이", "lock"]
    assert "frozen" in tokens and "instal" in tokens


def test_identifiers_are_kept_whole_in_addition_to_words() -> None:
    tokenizer = TextTokenizer("word", stem=True, identifiers=True)

    assert {"--frozen", "uv.lock"} <= set(tokenizer.tokenize(TEXT))
    assert tokenizer.name == "word+stem+ident"


def test_whitespace_rejects_word_options() -> None:
    with pytest.raises(ValueError):
        TextTokenizer("whitespace", stem=True)


def test_kiwi_analyzer_splits_particles_and_drops_punctuation() -> None:
    pytest.importorskip("kiwipiepy")

    tokens = TextTokenizer("kiwi").tokenize("uv.lock이 무엇인가요?")

    assert tokens[:2] == ["uv.lock", "이"]
    assert "?" not in tokens
