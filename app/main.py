"""FastAPI 앱 조립. lifespan에서 클라이언트를 한 번 만들고 인덱스 계약을 검증한 뒤에만 요청을 받는다."""
from fastapi import FastAPI
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from app.api.request_middleware import register_request_middleware
from app.service.query.query_builder import open_query_service
from app.common.logger import configure_logging, get_logger
from app.api.health_router import router as health_router
from app.api.error_mapper import register_error_handlers
from app.api.query_router import router as query_router
from app.common.settings import Settings, get_settings
from app.api.query_runtime import QueryRuntime

RuntimeBuilder = Callable[[Settings], AbstractAsyncContextManager[QueryRuntime]]

logger = get_logger(__name__)


@asynccontextmanager
async def build_runtime(settings: Settings) -> AsyncIterator[QueryRuntime]:
    """실제 클라이언트로 조립한다. 키, 엔드포인트, 인덱스 중 하나라도 없거나 계약이 다르면 기동을 멈춘다."""
    async with open_query_service(settings) as parts:
        logger.info("query_runtime_ready", collection=parts.collection, model=settings.answer_llm_model)
        yield QueryRuntime(settings=settings, service=parts.service, repository=parts.repository,
                           collection=parts.collection, contract=parts.contract)


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
