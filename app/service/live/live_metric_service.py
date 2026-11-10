"""대시보드 집계 조회. 저장소에서 실시간 기록과 현재 Judge 버전의 판정, Gold Set 기준선을 읽어 LiveSnapshot을 만든다."""
from app.service.eval.eval_summarizer import LanguageSummary, summarize_records
from app.service.live.live_aggregator import LiveSnapshot, build_snapshot
from app.repository.eval_record_repository import EvalRecordRepository
from app.schema.judge_schema import JudgeResult, RecordJudgment
from app.service.live.live_judge_worker import LiveJudgeWorker
from app.service.eval.judge_metric import aggregate
from app.schema.eval_schema import EvalRecord


class LiveMetricService:
    """기준선은 처음 한 번만 읽는다. 서버가 떠 있는 동안 Gold Set 평가 결과는 바뀌지 않는다고 본다."""

    def __init__(
        self, repository: EvalRecordRepository, worker: LiveJudgeWorker, config_id: str, threshold: float,
        judge_model: str, judge_versions: dict[str, str], limit: int, budget_krw: float,
    ) -> None:
        self._repository = repository
        self._worker = worker
        self._config_id = config_id
        self._threshold = threshold
        self._judge_model = judge_model
        self._versions = judge_versions
        self._limit = limit
        self._budget_krw = budget_krw
        self._baseline: tuple[str | None, list[EvalRecord], dict[str, RecordJudgment], list[LanguageSummary]] | None = None

    async def snapshot(self) -> LiveSnapshot:
        """최근 limit개 기록의 집계."""
        live = await self._repository.live_records(self._config_id, self._limit)
        judged = await self._judged([item.record for item in live])
        run_id, base_records, base_judged, gold = await self._load_baseline()
        return build_snapshot(
            self._config_id, live, judged, self._threshold, run_id, base_records, base_judged,
            self._worker.spent_krw, self._budget_krw, self._worker.exhausted, self._worker.sample_rate, gold,
        )

    async def _load_baseline(self) -> tuple[str | None, list[EvalRecord], dict[str, RecordJudgment], list[LanguageSummary]]:
        if self._baseline is None:
            run_id = await self._repository.latest_gold_run(self._config_id)
            records = await self._repository.records(run_id) if run_id else []
            judged = await self._judged(records)
            # Test set 탭은 평가 Report와 같은 요약 함수로 만든다. 문항 bootstrap이라 한 번만 계산해 둔다.
            self._baseline = (run_id, records, judged, summarize_records(records, self._threshold, judged) if records else [])
        return self._baseline

    async def _judged(self, records: list[EvalRecord]) -> dict[str, RecordJudgment]:
        answered = [r for r in records if r.status == "answered"]
        grouped: dict[str, list[JudgeResult]] = {}
        for result in await self._repository.judgments_for([r.record_id for r in answered]):
            if result.judge_model == self._judge_model and result.prompt_version == self._versions.get(result.kind):
                grouped.setdefault(result.record_id, []).append(result)
        # test set은 모든 문항에 정답 기준이 있어 Gold 기록만 정확성을 낸다. 실시간 질의에는 정답 기준이 없다.
        return {r.record_id: aggregate(r, grouped[r.record_id], has_criteria=r.source == "gold") for r in answered if r.record_id in grouped}
