"""실시간 누적 평가 조립. 평가 기록 저장소와 Judge를 열고, 둘 중 하나라도 없으면 평가만 끈 채 질의 서비스는 그대로 뜨게 한다."""
from openai import AsyncOpenAI
from dataclasses import dataclass
from psycopg import AsyncConnection
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.service.live.live_judge_worker import JudgeBudget, LiveJudgeWorker
from app.repository.eval_record_repository import EvalRecordRepository
from app.service.live.live_metric_service import LiveMetricService
from app.service.eval.pipeline_identity import pipeline_config_id
from app.service.eval.judge_service import JudgeService
from app.service.live.live_recorder import LiveRecorder
from app.service.query.query_builder import QueryParts
from app.service.eval.eval_service import TokenPrice
from app.service.live.live_signal import LiveSignal
from app.client.llm_client import LlmClient
from app.client.llm_cache import LlmCache
from app.common.settings import Settings
from app.common.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class LiveEval:
    """실시간 누적 평가 부품. 라우터가 응답 뒤 recorder를 부르고, 대시보드가 metrics와 signal을 쓴다."""

    recorder: LiveRecorder
    metrics: LiveMetricService
    signal: LiveSignal


@asynccontextmanager
async def open_live_eval(settings: Settings, parts: QueryParts) -> AsyncIterator[LiveEval | None]:
    """설정이 꺼져 있거나, 비밀번호나 Judge 엔드포인트가 없거나, 저장소에 연결하지 못하면 None을 낸다."""
    judge_url = settings.judge_llm_base_url or settings.llm_candidate_urls.get(settings.judge_llm_model)
    if not settings.live_eval_enabled or settings.eval_db_password is None or judge_url is None \
            or settings.elice_serverless_api_key is None:
        logger.warning("live_eval_disabled", enabled=settings.live_eval_enabled, db=settings.eval_db_password is not None,
                       judge=judge_url is not None)
        yield None
        return
    try:
        conn = await AsyncConnection.connect(
            host=settings.eval_db_host, port=settings.eval_db_port, dbname=settings.eval_db_name, user=settings.eval_db_user,
            password=settings.eval_db_password.get_secret_value(), autocommit=True, connect_timeout=5,
        )
    except Exception as e:
        # 평가 저장소는 부가 기능이라, 연결 실패가 질의 서비스 기동을 막지 않게 한다.
        logger.warning("live_eval_disabled", reason="eval db unavailable", error=type(e).__name__)
        yield None
        return
    repository = EvalRecordRepository(conn)
    sdk = AsyncOpenAI(api_key=settings.elice_serverless_api_key.get_secret_value(), base_url=judge_url,
                      timeout=settings.llm_timeout_seconds, max_retries=settings.llm_max_retries)
    try:
        await repository.ensure_schema()
        config_id = pipeline_config_id(settings, settings.default_top_k)
        signal = LiveSignal()
        judge = JudgeService(LlmClient(sdk, settings.judge_llm_model), LlmCache(settings.judge_cache_path), repository,
                             parts.retriever, settings.llm_concurrency)
        budget = JudgeBudget(input_krw_per_mtok=settings.judge_input_krw_per_mtok,
                             output_krw_per_mtok=settings.judge_output_krw_per_mtok, limit_krw=settings.live_judge_budget_krw)
        worker = LiveJudgeWorker(judge, repository, config_id, settings.default_top_k, settings.live_judge_sample_rate,
                                 budget, signal)
        price = TokenPrice(input_krw_per_mtok=settings.answer_input_krw_per_mtok,
                           output_krw_per_mtok=settings.answer_output_krw_per_mtok)
        recorder = LiveRecorder(repository, config_id, price, signal, worker.enqueue)
        metrics = LiveMetricService(repository, worker, config_id, settings.refusal_threshold, settings.judge_llm_model,
                                    {str(kind): version for kind, version in judge.versions.items()}, settings.live_snapshot_limit, settings.live_judge_budget_krw)
        await worker.start()
        logger.info("live_eval_ready", config_id=config_id, sample_rate=settings.live_judge_sample_rate,
                    budget_krw=settings.live_judge_budget_krw, spent_krw=worker.spent_krw)
        try:
            yield LiveEval(recorder=recorder, metrics=metrics, signal=signal)
        finally:
            await worker.stop()
    finally:
        await sdk.close()
        await conn.close()
