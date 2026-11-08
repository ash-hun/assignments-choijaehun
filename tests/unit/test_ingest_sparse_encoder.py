"""ingest 기능의 BM25 sparse 인코더(sparse_encoder) 단위 테스트."""
from app.service.ingest.sparse_encoder import Bm25Encoder
from app.common.text_tokenizer import TextTokenizer


def encoder() -> Bm25Encoder:
    return Bm25Encoder(TextTokenizer("word"))


def test_documents_saturate_term_frequency_and_normalize_length() -> None:
    short, long = encoder().encode_documents(["cache cache", "cache " + "other " * 8])
    cache = Bm25Encoder.hash_token("cache")

    weight_short = short.values[short.indices.index(cache)]
    weight_long = long.values[long.indices.index(cache)]
    assert weight_short > weight_long
    assert weight_short < 2.2


def test_query_marks_each_distinct_token_once_and_is_deterministic() -> None:
    query = encoder().encode_query("Cache cache lock")

    assert query.values == [1.0, 1.0]
    assert query == encoder().encode_query("lock CACHE")


def test_empty_batch_encodes_to_empty_list() -> None:
    assert encoder().encode_documents([]) == []
