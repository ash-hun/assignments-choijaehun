"""실시간 누적 평가 엔드포인트. 현재 집계(JSON), 갱신될 때마다 집계를 보내는 SSE, 대시보드 화면."""
from pathlib import Path
from typing import Annotated
from collections.abc import AsyncIterator
from fastapi.responses import FileResponse, StreamingResponse
from fastapi import Request, APIRouter, Depends, HTTPException

from app.api.query_runtime import QueryRuntime, get_runtime
from app.service.live.live_aggregator import LiveSnapshot
from app.service.live.live_builder import LiveEval
from app.api.api_key_guard import require_api_key

DASHBOARD = Path(__file__).parent / "static" / "metrics_dashboard.html"
# 변경이 없어도 이 간격마다 주석 줄을 보내 프록시가 연결을 끊지 않게 한다.
KEEPALIVE_SECONDS = 15.0

router = APIRouter(prefix="/v1", dependencies=[Depends(require_api_key)], tags=["metrics"])
page_router = APIRouter(tags=["metrics"])


def get_live(runtime: Annotated[QueryRuntime, Depends(get_runtime)]) -> LiveEval:
    """실시간 평가가 꺼져 있으면(저장소 비밀번호, Judge 엔드포인트 없음, 저장소 연결 실패) 503."""
    if runtime.live is None:
        raise HTTPException(status_code=503, detail="live evaluation is disabled")
    return runtime.live


@router.get(
    "/metrics",
    response_model=LiveSnapshot,
    summary="실시간 누적 지표",
    description=(
        "실제 질의(source=live) 최근 기록의 지표별 누적 평균, 95% 구간, 최근 50건 이동 창과 같은 구성의 Gold Set 기준선. "
        "reference=true인 지표는 검증 조건을 통과하지 못한 참고값이다. 읽기 전용이다."
    ),
    responses={401: {"description": "API 키 누락 또는 불일치"}, 503: {"description": "실시간 평가가 꺼져 있음"}},
)
async def metrics(live: Annotated[LiveEval, Depends(get_live)]) -> LiveSnapshot:
    """저장소에서 집계해 돌려준다."""
    return await live.metrics.snapshot()


@router.get(
    "/metrics/stream",
    summary="실시간 누적 지표(SSE)",
    description="연결 직후 snapshot 이벤트를 한 번 보내고, 기록이나 판정이 늘 때마다 새 snapshot을 보낸다. 변경이 없으면 15초마다 주석 줄을 보낸다.",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}, 401: {"description": "API 키 누락 또는 불일치"},
               503: {"description": "실시간 평가가 꺼져 있음"}},
)
async def metrics_stream(http: Request, live: Annotated[LiveEval, Depends(get_live)]) -> StreamingResponse:
    """클라이언트가 끊으면 루프를 끝낸다."""

    async def frames() -> AsyncIterator[str]:
        seen = live.signal.version
        yield _snapshot(await live.metrics.snapshot())
        while not await http.is_disconnected():
            version = await live.signal.wait(seen, KEEPALIVE_SECONDS)
            if version == seen:
                yield ": keepalive\n\n"
                continue
            seen = version
            yield _snapshot(await live.metrics.snapshot())

    return StreamingResponse(frames(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@page_router.get("/dashboard", include_in_schema=False)
async def dashboard() -> FileResponse:
    """정적 화면. 데이터는 화면이 /v1/metrics/stream에서 직접 받는다(API 키는 화면에서 입력)."""
    return FileResponse(DASHBOARD, media_type="text/html")


def _snapshot(snapshot: LiveSnapshot) -> str:
    return f"event: snapshot\ndata: {snapshot.model_dump_json()}\n\n"
