"""Gold Set 평가 실행. 문항마다 실제 질의 경로(스트리밍)로 답을 받고, 검색 지표와 운영 수치를 기록 저장소에 남긴다."""
import asyncio
from pydantic import BaseModel

from app.service.eval.retrieval_metric import rank_score, relevant_chunk_ids
from app.repository.eval_record_repository import EvalRecordRepository
from app.schema.query_schema import StreamToken, QueryResponse
from app.service.query.chunk_retriever import ChunkRetriever
from app.schema.eval_schema import EvalConfig, EvalRecord
from app.service.query.query_service import QueryService
from app.common.upstream_error import UpstreamError
from app.schema.gold_schema import GoldItem
from app.schema.chunk_schema import Chunk
from app.common.logger import get_logger

logger = get_logger(__name__)


class TokenPrice(BaseModel):
    """답변 모델의 100만 토큰당 원화 단가(VAT 별도)."""

    input_krw_per_mtok: float
    output_krw_per_mtok: float


class EvalOutcome(BaseModel):
    """실행 결과. 실패한 문항은 기록하지 않아 다시 돌리면 그 문항만 새로 부른다."""

    records: list[EvalRecord]
    reused: int
    failed: list[str]


class EvalService:
    """이미 기록된 문항은 다시 부르지 않는다. 같은 run_id로 다시 돌리면 비용 0으로 같은 기록이 나온다."""

    def __init__(
        self, query: QueryService, retriever: ChunkRetriever, repository: EvalRecordRepository, price: TokenPrice,
    ) -> None:
        self._query = query
        self._retriever = retriever
        self._repository = repository
        self._price = price

    async def run(
        self, run_id: str, config_id: str, config: EvalConfig, items: list[GoldItem], index_chunks: list[Chunk],
    ) -> EvalOutcome:
        """기록이 없는 문항만 동시에 config.concurrency개씩 돌린다. 결과는 record_id 순이다."""
        existing = {r.item_id: r for r in await self._repository.records(run_id)}
        todo = [item for item in items if str(item.id) not in existing]
        semaphore = asyncio.Semaphore(config.concurrency)
        failed: list[str] = []

        async def one(item: GoldItem) -> EvalRecord | None:
            async with semaphore:
                try:
                    record = await self._evaluate(run_id, config_id, config, item, index_chunks)
                except UpstreamError as e:
                    logger.warning("eval_item_failed", item=str(item.id), error=type(e).__name__, cause=type(e.__cause__).__name__)
                    failed.append(str(item.id))
                    return None
            await self._repository.upsert_record(record)
            return record

        fresh = [r for r in await asyncio.gather(*(one(item) for item in todo)) if r is not None]
        records = sorted([*existing.values(), *fresh], key=lambda r: r.record_id)
        logger.info("eval_run_done", run_id=run_id, total=len(records), reused=len(existing), new=len(fresh), failed=len(failed))
        return EvalOutcome(records=records, reused=len(existing), failed=sorted(failed))

    async def _evaluate(
        self, run_id: str, config_id: str, config: EvalConfig, item: GoldItem, index_chunks: list[Chunk],
    ) -> EvalRecord:
        rank = None
        retrieved: list[str] = []
        if item.answerable:
            ranked = [hit.chunk for hit in await self._retriever.retrieve(item.question, config.retrieval_depth)]
            retrieved = [c.chunk_id for c in ranked]
            rank = rank_score(item, ranked, relevant_chunk_ids(item, index_chunks))
        response = await self._answer(item.question, config.top_k)
        meta, usage = response.meta, response.meta.usage
        refused = response.status == "insufficient_context"
        return EvalRecord(
            record_id=f"{run_id}:{item.id}", run_id=run_id, source="gold", config_id=config_id, item_id=str(item.id),
            language=item.language, type=item.type, answerable=item.answerable, question=item.question,
            status=response.status,
            refusal_stage=("retrieval" if usage.output_tokens == 0 else "generation") if refused else None,
            answer=response.answer, cited_chunk_ids=[c.chunk_id for c in response.citations],
            dropped_citations=meta.dropped_citations, retrieved_chunk_ids=retrieved, retrieval_scores=meta.retrieval_scores,
            top_score=meta.retrieval_scores[0] if meta.retrieval_scores else None, rank=rank,
            retrieval_ms=meta.retrieval_ms, first_token_ms=meta.first_token_ms, latency_ms=meta.latency_ms,
            input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
            cost_krw=round(usage.input_tokens * self._price.input_krw_per_mtok / 1e6
                           + usage.output_tokens * self._price.output_krw_per_mtok / 1e6, 4),
        )

    async def _answer(self, question: str, top_k: int) -> QueryResponse:
        """스트리밍 경로로 답을 받아 마지막 QueryResponse만 쓴다. TTFT가 같은 호출에서 함께 잰다."""
        final: QueryResponse | None = None
        async for event in self._query.answer_stream(question, top_k):
            if not isinstance(event, StreamToken):
                final = event
        if final is None:
            raise UpstreamError("query stream ended without a response")
        return final
