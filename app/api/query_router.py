"""질의응답 엔드포인트."""
from typing import Annotated
from fastapi import APIRouter, Depends

from app.schema.query_schema import QueryRequest, QueryResponse
from app.api.query_runtime import QueryRuntime, get_runtime
from app.api.api_key_guard import require_api_key

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
