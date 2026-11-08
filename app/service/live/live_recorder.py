"""실시간 질의 기록. 응답이 나간 뒤 기록 저장소에 남기고 채점 대기열에 넣는다. 실패해도 응답에는 영향이 없다."""
from collections.abc import Awaitable, Callable

from app.repository.eval_record_repository import EvalRecordRepository
from app.service.eval.eval_service import TokenPrice
from app.service.live.live_signal import LiveSignal
from app.schema.query_schema import QueryResponse
from app.schema.eval_schema import EvalRecord
from app.common.logger import get_logger

logger = get_logger(__name__)


class LiveRecorder:
    """요청 id가 기록 키라 같은 요청을 다시 기록해도 행이 늘지 않는다."""

    def __init__(
        self, repository: EvalRecordRepository, config_id: str, price: TokenPrice, signal: LiveSignal,
        on_recorded: Callable[[EvalRecord], Awaitable[None]],
    ) -> None:
        self._repository = repository
        self._config_id = config_id
        self._price = price
        self._signal = signal
        self._on_recorded = on_recorded

    async def record(self, request_id: str, question: str, response: QueryResponse) -> None:
        """저장, 채점 대기열 추가, 변경 알림 순. 어느 단계에서 실패해도 로그만 남긴다."""
        meta, usage = response.meta, response.meta.usage
        refused = response.status == "insufficient_context"
        record = EvalRecord(
            record_id=f"live:{request_id}", run_id=None, source="live", config_id=self._config_id, item_id=None,
            language=None, type=None, answerable=None, question=question, status=response.status,
            refusal_stage=("retrieval" if usage.output_tokens == 0 else "generation") if refused else None,
            answer=response.answer, cited_chunk_ids=[c.chunk_id for c in response.citations],
            dropped_citations=meta.dropped_citations, retrieved_chunk_ids=[], retrieval_scores=meta.retrieval_scores,
            top_score=meta.retrieval_scores[0] if meta.retrieval_scores else None, rank=None,
            retrieval_ms=meta.retrieval_ms, first_token_ms=meta.first_token_ms, latency_ms=meta.latency_ms,
            input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
            cost_krw=round(usage.input_tokens * self._price.input_krw_per_mtok / 1e6
                           + usage.output_tokens * self._price.output_krw_per_mtok / 1e6, 4),
        )
        try:
            await self._repository.upsert_record(record)
            await self._signal.publish()
            await self._on_recorded(record)
        except Exception as e:
            # 평가 기록은 서비스 응답의 부가 기능이라, 저장소 장애가 질의 응답을 깨지 않게 모든 예외를 여기서 끊는다.
            logger.warning("live_record_failed", record=record.record_id, error=type(e).__name__)
