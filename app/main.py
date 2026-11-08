"""FastAPI 앱 조립. lifespan에서 클라이언트를 한 번 만들고 인덱스 계약을 검증한 뒤에만 요청을 받는다."""
from fastapi import FastAPI
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from app.repository.qdrant_chunk_repository import QdrantChunkRepository
from app.api.request_middleware import register_request_middleware
from app.service.query.evidence_checker import EvidenceChecker
from app.service.query.chunk_retriever import ChunkRetriever
from app.common.logger import configure_logging, get_logger
from app.api.health_router import router as health_router
from app.service.query.query_service import QueryService
from app.api.error_mapper import register_error_handlers
from app.client.embedding_client import EmbeddingClient
from app.api.query_router import router as query_router
from app.common.settings import Settings, get_settings
from app.service.query.llm_gate import LlmGate
from app.api.query_runtime import QueryRuntime
from app.client.llm_client import LlmClient

RuntimeBuilder = Callable[[Settings], AbstractAsyncContextManager[QueryRuntime]]

logger = get_logger(__name__)


@asynccontextmanager
async def build_runtime(settings: Settings) -> AsyncIterator[QueryRuntime]:
    """실제 클라이언트로 조립한다. 키, 엔드포인트, 인덱스 중 하나라도 없거나 계약이 다르면 기동을 멈춘다."""
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
    service = QueryService(
        ChunkRetriever(repository, embedding, collection), EvidenceChecker(settings.refusal_threshold),
        LlmClient(sdk, settings.answer_llm_model), LlmGate(settings.llm_concurrency, settings.llm_queue_timeout_seconds),
        settings.embedding_model, settings.default_top_k, settings.answer_temperature, settings.answer_seed, settings.answer_max_tokens,
    )
    logger.info("query_runtime_ready", collection=collection, model=settings.answer_llm_model)
    try:
        yield QueryRuntime(settings=settings, service=service, repository=repository, collection=collection, contract=contract)
    finally:
        await sdk.close()
        await qdrant.close()


def create_app(settings: Settings, builder: RuntimeBuilder = build_runtime) -> FastAPI:
    """builder를 바꾸면 외부 의존 없이 같은 앱을 띄울 수 있다(통합 테스트)."""
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with builder(settings) as runtime:
            app.state.runtime = runtime
            yield

    app = FastAPI(title="uv docs RAG QA", version="1.0.0", lifespan=lifespan,
                  description="uv 공식 문서를 근거로 답하고 출처를 붙이며, 근거가 없으면 답하지 않는 질의응답 API.")
    register_request_middleware(app)
    register_error_handlers(app, settings.llm_queue_timeout_seconds)
    app.include_router(health_router)
    app.include_router(query_router)
    return app


app = create_app(get_settings())
