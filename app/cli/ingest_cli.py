"""Ingest 진입점. manifest에 고정된 원문을 확정 구성(임베딩, Chunking, BM25 토큰화)으로 색인한다."""
import sys
import asyncio
from typing import cast, get_args
from qdrant_client import AsyncQdrantClient

from app.service.ingest.ingest_service import IngestResult, IngestService
from app.repository.qdrant_chunk_repository import QdrantChunkRepository
from app.service.ingest.chunk_splitter import ChunkMethod, ChunkSplitter
from app.service.ingest.document_loader import load_documents
from app.service.ingest.sparse_encoder import SparseEncoder
from app.client.embedding_client import EmbeddingClient
from app.common.settings import Settings, get_settings
from app.common.text_tokenizer import TextTokenizer
from app.schema.corpus_schema import CorpusManifest
from app.common.logger import get_logger

logger = get_logger(__name__)


async def run(settings: Settings) -> IngestResult:
    """원문을 읽고 색인한다. 같은 원문과 설정으로 다시 돌리면 같은 상태가 된다."""
    if settings.chunk_method not in get_args(ChunkMethod) or settings.chunk_method == "semantic":
        raise SystemExit(f"unsupported CHUNK_METHOD for ingest: {settings.chunk_method}")
    manifest_path = settings.data_dir / "corpus" / "manifests" / f"{settings.corpus_name}.json"
    manifest = CorpusManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    documents = load_documents(manifest, settings.data_dir / "corpus" / "raw" / settings.corpus_name)
    embedding = EmbeddingClient(settings.embedding_model, settings.model_cache_dir, settings.embedding_query_prefix)
    splitter = ChunkSplitter(cast(ChunkMethod, settings.chunk_method), settings.chunk_size, settings.chunk_overlap,
                             embedding.token_count, embedding.token_offsets)
    repository = QdrantChunkRepository(AsyncQdrantClient(url=settings.qdrant_url, timeout=60))
    service = IngestService(repository, embedding, splitter, SparseEncoder(TextTokenizer(settings.bm25_tokenizer)),
                            settings.index_contract(), settings.corpus_name)
    urls = {f.path: manifest.file_url(f.path) for f in manifest.files}
    return await service.run(documents, urls)


def main() -> int:
    """색인하고 결과를 로그로 남긴다."""
    asyncio.run(run(get_settings()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
