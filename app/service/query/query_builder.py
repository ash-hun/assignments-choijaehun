"""설정에서 질의응답 파이프라인을 조립한다. API 서버와 Gold Set 평가가 같은 조립을 써서 평가 대상과 서비스가 같다."""
from openai import AsyncOpenAI
from dataclasses import dataclass
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from qdrant_client import AsyncQdrantClient

from app.service.query.chunk_retriever import FusionSettings, ChunkRetriever
from app.repository.qdrant_chunk_repository import QdrantChunkRepository
from app.service.query.evidence_checker import EvidenceChecker
from app.service.ingest.sparse_encoder import SparseEncoder
from app.service.query.query_service import QueryService
from app.client.embedding_client import EmbeddingClient
from app.common.text_tokenizer import TextTokenizer
from app.schema.vector_schema import IndexContract
from app.service.query.llm_gate import LlmGate
from app.client.llm_client import LlmClient
from app.common.settings import Settings


@dataclass(frozen=True)
class QueryParts:
    """조립한 서비스와, 평가와 상태 확인이 함께 쓰는 하위 부품."""

    service: QueryService
    retriever: ChunkRetriever
    llm: LlmClient
    gate: LlmGate
    repository: QdrantChunkRepository
    collection: str
    contract: IndexContract


@asynccontextmanager
async def open_query_service(settings: Settings) -> AsyncIterator[QueryParts]:
    """키, 엔드포인트, 인덱스 중 하나라도 없거나 인덱스 계약이 다르면 RuntimeError로 멈춘다. 나갈 때 연결을 닫는다."""
    if settings.elice_serverless_api_key is None or settings.answer_llm_base_url is None:
        raise RuntimeError("ELICE_SERVERLESS_API_KEY and ANSWER_LLM_BASE_URL must be set")
    contract = settings.index_contract()
    collection = contract.collection_name(settings.corpus_name)
    qdrant = AsyncQdrantClient(url=settings.qdrant_url, timeout=10)
    repository = QdrantChunkRepository(qdrant)
    stored = await repository.read_contract(collection)
    if stored != contract:
        await qdrant.close()
        raise RuntimeError(f"index contract mismatch for {collection}: run `make ingest` with the same settings")
    embedding = EmbeddingClient(settings.embedding_model, settings.model_cache_dir, settings.embedding_query_prefix)
    sdk = AsyncOpenAI(api_key=settings.elice_serverless_api_key.get_secret_value(), base_url=settings.answer_llm_base_url,
                      timeout=settings.llm_timeout_seconds, max_retries=settings.llm_max_retries)
    fusion = FusionSettings(mode=settings.retrieval_mode, pool=settings.fusion_pool, rrf_k=settings.rrf_k, cc_alpha=settings.cc_alpha)
    # 질의 쪽 BM25는 Ingest와 같은 토크나이저여야 한다. 토크나이저는 인덱스 계약에 들어 있어 위에서 이미 맞춰 봤다.
    retriever = ChunkRetriever(repository, embedding, collection, SparseEncoder(TextTokenizer(settings.bm25_tokenizer)), fusion)
    llm = LlmClient(sdk, settings.answer_llm_model)
    gate = LlmGate(settings.llm_concurrency, settings.llm_queue_timeout_seconds)
    service = QueryService(
        retriever, EvidenceChecker(settings.refusal_threshold), llm, gate,
        settings.embedding_model, settings.default_top_k, settings.answer_temperature, settings.answer_seed, settings.answer_max_tokens,
    )
    try:
        yield QueryParts(service=service, retriever=retriever, llm=llm, gate=gate, repository=repository, collection=collection,
                         contract=contract)
    finally:
        await sdk.close()
        await qdrant.close()
