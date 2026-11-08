"""요청 추적 미들웨어. X-Request-ID를 받거나 만들어 모든 로그에 묶고, 응답 헤더와 처리 시간 로그로 남긴다."""
import re
import time
import uuid
import structlog
from fastapi import FastAPI, Request, Response
from collections.abc import Awaitable, Callable

from app.common.logger import get_logger

# 로그 주입을 막으려고 클라이언트가 보낸 값은 이 형식일 때만 그대로 쓴다.
REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")

logger = get_logger(__name__)


def register_request_middleware(app: FastAPI) -> None:
    """요청마다 contextvars를 비우고 새 요청 ID를 묶는다."""

    @app.middleware("http")
    async def track(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        incoming = request.headers.get("x-request-id", "")
        request_id = incoming if REQUEST_ID.match(incoming) else uuid.uuid4().hex
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logger.info("request_done", method=request.method, path=request.url.path, status=response.status_code,
                    latency_ms=int((time.perf_counter() - started) * 1000))
        return response
