"""외부 의존 실패를 HTTP 상태로 바꾼다. 응답 본문에는 내부 예외 메시지와 주소를 넣지 않고, 요청 ID로 로그를 찾게 한다."""
import math
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.common.upstream_error import LlmBusyError, UpstreamError, LlmTimeoutError, LlmFailureError, VectorStoreError
from app.common.logger import get_logger

logger = get_logger(__name__)

# 예외 종류별 (상태, 사람이 읽을 메시지).
MAPPING: list[tuple[type[UpstreamError], int, str]] = [
    (LlmBusyError, 503, "too many concurrent requests, retry later"),
    (VectorStoreError, 503, "vector store unavailable"),
    (LlmTimeoutError, 504, "llm request timed out"),
    (LlmFailureError, 502, "llm request failed"),
]


def describe(error: Exception) -> tuple[int, str]:
    """예외의 HTTP 상태와 공개 메시지. 스트림 도중 실패를 error 이벤트로 보낼 때도 같은 표를 쓴다."""
    return next(((s, d) for kind, s, d in MAPPING if isinstance(error, kind)), (502, "upstream failure"))


def register_error_handlers(app: FastAPI, retry_after_seconds: float) -> None:
    """UpstreamError 하위 예외를 한 곳에서 처리한다."""

    async def handle(request: Request, error: Exception) -> JSONResponse:
        status, detail = describe(error)
        logger.warning("upstream_error", kind=type(error).__name__, status=status, cause=type(error.__cause__).__name__)
        headers = {"Retry-After": str(math.ceil(retry_after_seconds))} if isinstance(error, LlmBusyError) else None
        return JSONResponse(status_code=status, content={"detail": detail}, headers=headers)

    app.add_exception_handler(UpstreamError, handle)
