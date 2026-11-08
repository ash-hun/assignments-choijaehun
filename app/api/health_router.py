"""상태 확인 엔드포인트. /health는 프로세스 생존, /ready는 벡터 DB 연결과 인덱스 계약 일치를 본다."""
from typing import Annotated
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.api.query_runtime import QueryRuntime, get_runtime
from app.common.upstream_error import VectorStoreError

router = APIRouter(tags=["health"])


@router.get("/health", summary="프로세스 생존 확인", description="항상 200. 외부 의존을 보지 않는다.")
async def health() -> dict[str, str]:
    """프로세스가 요청을 받을 수 있으면 200."""
    return {"status": "ok"}


@router.get(
    "/ready", summary="요청 처리 준비 확인",
    description="벡터 DB에 연결되고 컬렉션의 인덱스 계약이 서버 설정과 같으면 200, 아니면 503.",
    responses={503: {"description": "벡터 DB 연결 실패 또는 인덱스 계약 불일치"}},
)
async def ready(runtime: Annotated[QueryRuntime, Depends(get_runtime)]) -> JSONResponse:
    """기동 후 인덱스가 바뀌었는지도 잡는다."""
    try:
        contract = await runtime.repository.read_contract(runtime.collection)
    except VectorStoreError:
        return JSONResponse(status_code=503, content={"status": "unavailable", "detail": "vector store unavailable"})
    if contract != runtime.contract:
        return JSONResponse(status_code=503, content={"status": "unavailable", "detail": "index contract mismatch"})
    return JSONResponse(status_code=200, content={"status": "ready", "collection": runtime.collection})
