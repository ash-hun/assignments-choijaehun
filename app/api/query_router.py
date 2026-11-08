"""질의응답 엔드포인트. 비스트리밍 JSON 응답과 SSE 스트리밍 응답."""
import json
from typing import Annotated
from pydantic import BaseModel
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from collections.abc import AsyncIterator, AsyncGenerator

from app.schema.query_schema import StreamToken, QueryRequest, QueryResponse
from app.api.query_runtime import QueryRuntime, get_runtime
from app.common.upstream_error import UpstreamError
from app.api.api_key_guard import require_api_key
from app.api.error_mapper import describe
from app.common.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/v1", dependencies=[Depends(require_api_key)], tags=["query"])


@router.post(
    "/query",
    response_model=QueryResponse,
    summary="문서 근거 기반 질의응답",
    description=(
        "질문을 검색해 찾은 근거만으로 답하고, 본문의 [n] 인용을 출처 목록으로 돌려준다. "
        "검색 최고 점수가 임계값 미만이거나 모델이 근거 부족을 알리면 status=insufficient_context(200)로 답하지 않는다. "
        "읽기 전용이라 다시 호출해도 서버 상태는 바뀌지 않는다."
    ),
    responses={401: {"description": "API_KEY가 설정됐는데 X-API-Key가 없거나 틀림"},
               502: {"description": "LLM 호출 실패"}, 503: {"description": "벡터 DB 연결 실패 또는 동시 호출 상한 초과"},
               504: {"description": "LLM 타임아웃"}},
)
async def query(request: QueryRequest, runtime: Annotated[QueryRuntime, Depends(get_runtime)]) -> QueryResponse:
    """서비스 결과를 그대로 돌려준다."""
    return await runtime.service.answer(request.question, request.top_k)


@router.post(
    "/query/stream",
    summary="문서 근거 기반 질의응답(SSE 스트리밍)",
    description=(
        "/v1/query와 같은 요청을 받아 text/event-stream으로 응답한다. 생성 텍스트는 token 이벤트로 흘리고, "
        "검증한 인용과 메타는 final 이벤트로 한 번 보낸다. 검색 단계에서 거절되면 final만 보낸다. "
        "첫 이벤트 전에 난 실패는 일반 HTTP 에러로, 그 뒤의 실패는 error 이벤트로 알린다. "
        "token 텍스트의 [n]은 검증 전이므로 인용은 final의 citations를 기준으로 렌더링한다."
    ),
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}, 401: {"description": "API 키 누락 또는 불일치"},
               502: {"description": "첫 이벤트 전 LLM 호출 실패"}, 503: {"description": "벡터 DB 장애 또는 동시 호출 상한 초과"},
               504: {"description": "첫 이벤트 전 LLM 타임아웃"}},
)
async def query_stream(request: QueryRequest, runtime: Annotated[QueryRuntime, Depends(get_runtime)]) -> StreamingResponse:
    """첫 이벤트를 받은 뒤에 응답을 시작해, 검색 실패나 동시 호출 상한 초과는 상태 코드로 돌려준다."""
    events = runtime.service.answer_stream(request.question, request.top_k)
    first = await anext(events)
    return StreamingResponse(_sse(first, events), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


async def _sse(first: StreamToken | QueryResponse, events: AsyncGenerator[StreamToken | QueryResponse, None]) -> AsyncIterator[str]:
    try:
        yield _event(first)
        async for event in events:
            yield _event(event)
    except UpstreamError as error:
        status, detail = describe(error)
        logger.warning("stream_error", kind=type(error).__name__, status=status)
        yield _frame("error", {"detail": detail, "status_code": status})
    finally:
        # 클라이언트가 끊으면 생성기를 닫아 LLM 동시 호출 자리를 돌려준다.
        await events.aclose()


def _event(event: StreamToken | QueryResponse) -> str:
    return _frame("token" if isinstance(event, StreamToken) else "final", event)


def _frame(name: str, data: BaseModel | dict[str, object]) -> str:
    payload = data.model_dump_json() if isinstance(data, BaseModel) else json.dumps(data, ensure_ascii=False)
    return f"event: {name}\ndata: {payload}\n\n"
