"""ingest 기능의 통합 테스트. 분할, 임베딩, sparse 인코딩, 저장, 사라진 청크 정리를 메모리 저장소로 이어서 돌린다."""
import asyncio

from tests.integ.memory_backend import MemoryChunkRepository, MemoryEmbeddingClient
from app.service.ingest.ingest_service import IngestResult, IngestService
from app.service.ingest.sparse_encoder import SparseEncoder
from app.service.ingest.chunk_splitter import ChunkSplitter
from app.common.text_tokenizer import TextTokenizer
from app.schema.chunk_schema import Document
from app.common.settings import Settings

CACHE = Document(doc_id="cache.md", title="Cache", text="# Cache\n\nThe cache directory can be moved with UV_CACHE_DIR.\n")
LOCK = Document(doc_id="lock.md", title="Lock", text="# Lock\n\nThe lockfile records exact resolved versions.\n")


def ingest(repository: MemoryChunkRepository, documents: list[Document]) -> IngestResult:
    embedding = MemoryEmbeddingClient()
    splitter = ChunkSplitter("structure", 40, 0, embedding.token_count, embedding.token_offsets)
    contract = Settings(_env_file=None).index_contract()
    service = IngestService(repository, embedding, splitter, SparseEncoder(TextTokenizer("word")), contract, "uv_docs")
    urls = {d.doc_id: f"https://example/{d.doc_id}" for d in documents}
    return asyncio.run(service.run(documents, urls))


def test_rerun_converges_to_the_same_points_and_records_the_contract() -> None:
    repository = MemoryChunkRepository()

    first = ingest(repository, [CACHE, LOCK])
    second = ingest(repository, [CACHE, LOCK])

    stored = repository.chunks[first.collection]
    assert (first.chunks, second.chunks, second.removed) == (len(stored), len(stored), 0)
    assert repository.contracts[first.collection] == Settings(_env_file=None).index_contract()
    assert {c.url for c in stored.values()} == {"https://example/cache.md", "https://example/lock.md"}


def test_chunks_of_a_removed_document_are_deleted_on_rerun() -> None:
    repository = MemoryChunkRepository()
    ingest(repository, [CACHE, LOCK])

    result = ingest(repository, [CACHE])

    assert result.removed >= 1
    assert {c.doc_id for c in repository.chunks[result.collection].values()} == {"cache.md"}
