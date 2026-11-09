"""query 기능의 검색 방식 선택(chunk_retriever.mode_for) 단위 테스트."""
import pytest

from tests.integ.memory_backend import MemoryChunkRepository, MemoryEmbeddingClient
from app.service.query.chunk_retriever import FusionSettings, ChunkRetriever
from app.service.ingest.sparse_encoder import SparseEncoder
from app.common.text_tokenizer import TextTokenizer
from app.schema.query_schema import RetrievalMode


def retriever(mode: RetrievalMode) -> ChunkRetriever:
    return ChunkRetriever(MemoryChunkRepository(), MemoryEmbeddingClient(), "c", SparseEncoder(TextTokenizer("word")),
                          FusionSettings(mode=mode))


def test_routed_picks_dense_for_hangul_and_cc_otherwise() -> None:
    routed = retriever("routed")

    assert routed.mode_for("UV_CACHE_DIR는 어디에 쓰나요?") == "dense"
    assert routed.mode_for("Where does UV_CACHE_DIR point?") == "cc"
    assert retriever("rrf").mode_for("캐시 위치") == "rrf"


def test_non_dense_mode_without_a_sparse_encoder_is_rejected() -> None:
    with pytest.raises(ValueError):
        ChunkRetriever(MemoryChunkRepository(), MemoryEmbeddingClient(), "c", None, FusionSettings(mode="cc"))
