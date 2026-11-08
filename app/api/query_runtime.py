"""API 서버가 요청 사이에 공유하는 객체 묶음. lifespan에서 한 번 만들고 종료 시 닫는다."""
from fastapi import Request
from dataclasses import dataclass

from app.repository.qdrant_chunk_repository import QdrantChunkRepository
from app.service.query.query_service import QueryService
from app.schema.vector_schema import IndexContract
from app.common.settings import Settings


@dataclass(frozen=True)
class QueryRuntime:
    """질의 서비스와, /ready가 인덱스 계약을 다시 대조할 저장소, 기대 계약."""

    settings: Settings
    service: QueryService
    repository: QdrantChunkRepository
    collection: str
    contract: IndexContract


def get_runtime(request: Request) -> QueryRuntime:
    """라우터 의존성. lifespan이 app.state에 넣어 둔 객체를 꺼낸다."""
    runtime: QueryRuntime = request.app.state.runtime
    return runtime
