"""실시간 질의의 백그라운드 Judge. 대기열에서 답한 기록을 꺼내 1회 판정하고, 샘플링 비율과 예산 상한을 지킨다."""
import asyncio
import hashlib
from pydantic import BaseModel

from app.repository.eval_record_repository import EvalRecordRepository
from app.service.eval.judge_service import JudgeService
from app.service.live.live_signal import LiveSignal
from app.schema.eval_schema import EvalRecord
from app.common.logger import get_logger

# 재시작 뒤 한 번에 다시 꺼내는 채점 대기 기록 수. 넘는 분량은 다음 재시작이나 새 기록과 함께 처리된다.
BACKLOG_LIMIT = 500
QUEUE_SIZE = 1000

logger = get_logger(__name__)


class JudgeBudget(BaseModel):
    """Judge 단가와 상한(원, VAT 별도). 상한을 넘으면 채점만 멈추고 기록은 계속 쌓인다.

    저장된 판정의 토큰 수로 세서, 캐시에서 받은 판정도 비용으로 센다. 실제 지출보다 크게 잡히는 쪽이라 상한을 넘지 않는다.
    """

    input_krw_per_mtok: float
    output_krw_per_mtok: float
    limit_krw: float

    def spent(self, input_tokens: int, output_tokens: int) -> float:
        """토큰 수를 원화로 바꾼다."""
        return input_tokens * self.input_krw_per_mtok / 1e6 + output_tokens * self.output_krw_per_mtok / 1e6


def sampled(record_id: str, rate: float) -> bool:
    """기록 id의 해시로 정해 같은 기록은 언제 돌려도 같은 결정이 나온다."""
    if rate >= 1.0:
        return True
    bucket = int(hashlib.sha256(record_id.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return bucket < rate


class LiveJudgeWorker:
    """대기열은 크기가 정해져 있어 Judge가 밀려도 메모리가 늘지 않는다. 넘친 기록은 재시작 때 저장소에서 다시 꺼낸다."""

    def __init__(
        self, judge: JudgeService, repository: EvalRecordRepository, config_id: str, top_k: int,
        sample_rate: float, budget: JudgeBudget, signal: LiveSignal,
    ) -> None:
        self._judge = judge
        self._repository = repository
        self._config_id = config_id
        self._top_k = top_k
        self._sample_rate = sample_rate
        self._budget = budget
        self._signal = signal
        self._queue: asyncio.Queue[EvalRecord] = asyncio.Queue(QUEUE_SIZE)
        self._spent_krw = 0.0
        self._task: asyncio.Task[None] | None = None

    @property
    def spent_krw(self) -> float:
        """실시간 채점에 쓴 누적 비용."""
        return round(self._spent_krw, 1)

    @property
    def sample_rate(self) -> float:
        """채점할 기록의 비율."""
        return self._sample_rate

    @property
    def exhausted(self) -> bool:
        """예산 상한에 닿았는지."""
        return self._spent_krw >= self._budget.limit_krw

    async def start(self) -> None:
        """누적 비용을 저장소에서 읽고, 채점이 안 된 기록을 대기열에 넣은 뒤 작업을 띄운다."""
        self._spent_krw = self._budget.spent(*await self._repository.live_judge_tokens())
        versions = list(self._judge.versions.values())
        for record in await self._repository.unjudged_live(self._config_id, versions, BACKLOG_LIMIT):
            await self.enqueue(record)
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        """작업을 취소하고 끝나기를 기다린다."""
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def enqueue(self, record: EvalRecord) -> None:
        """답한 기록 중 표본에 든 것만 넣는다. 대기열이 차면 버리고, 저장소에 남아 재시작 때 다시 꺼낸다."""
        if record.status != "answered" or not sampled(record.record_id, self._sample_rate):
            return
        try:
            self._queue.put_nowait(record)
        except asyncio.QueueFull:
            logger.warning("live_judge_queue_full", record=record.record_id)

    async def _run(self) -> None:
        while True:
            record = await self._queue.get()
            if self.exhausted:
                logger.warning("live_judge_budget_exhausted", spent_krw=self.spent_krw, limit_krw=self._budget.limit_krw)
                continue
            try:
                await self._judge.judge([record], {}, 1, self._top_k)
                # 이미 있던 판정을 두 번 세지 않게, 증분을 더하지 않고 저장소의 합계를 다시 읽는다.
                self._spent_krw = self._budget.spent(*await self._repository.live_judge_tokens())
            except Exception as e:
                # 작업자 하나가 죽으면 이후 채점이 모두 멈춘다. 기록 하나의 실패는 로그로 남기고 다음 기록으로 간다.
                logger.warning("live_judge_failed", record=record.record_id, error=type(e).__name__)
                continue
            await self._signal.publish()
