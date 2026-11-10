"""평가 기록 저장소 스냅샷. 실시간 질의 내역과 대시보드 기준선(Gold 실행)을 JSONL로 내보내고, 다른 환경의 저장소에 다시 넣는다."""
import json
from pathlib import Path
from pydantic import ValidationError

from app.schema.history_schema import HistoryRun, HistoryLine, HistoryCounts, HistoryRecord, HistoryJudgment
from app.repository.eval_record_repository import EvalRecordRepository
from app.schema.judge_schema import JudgeResult
from app.schema.eval_schema import LiveRecord
from app.common.logger import get_logger

logger = get_logger(__name__)


class HistorySnapshot:
    """파일은 정렬된 줄이라, 저장소 내용이 같으면 몇 번 내보내도 같은 파일이 된다(git diff가 생기지 않는다)."""

    def __init__(self, repository: EvalRecordRepository) -> None:
        self._repository = repository

    async def export(self, path: Path, config_ids: list[str]) -> HistoryCounts:
        """실시간 기록 전부와, 그 기록들의 구성과 config_ids 각각의 대시보드 기준선 실행을 판정과 함께 쓴다."""
        live = await self._repository.history_records([])
        wanted = sorted(set(config_ids) | {item.record.config_id for item in live})
        run_ids = sorted({run for c in wanted if (run := await self._repository.latest_gold_run(c)) is not None})
        runs = await self._repository.history_runs(run_ids)
        records = await self._repository.history_records(run_ids)
        judgments = sorted(await self._repository.judgments_for([item.record.record_id for item in records]),
                           key=lambda j: (j.record_id, j.kind, j.sample, j.judge_model, j.prompt_version))
        lines = [*(HistoryLine(line=r) for r in runs),
                 *(HistoryLine(line=HistoryRecord(item=r)) for r in records),
                 *(HistoryLine(line=HistoryJudgment(result=j)) for j in judgments)]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(line.model_dump(mode="json")["line"], ensure_ascii=False, sort_keys=True) + "\n"
                                for line in lines), encoding="utf-8")
        return HistoryCounts(runs=len(runs), records=len(records), judgments=len(judgments))

    async def load(self, path: Path) -> HistoryCounts:
        """파일이 없으면 아무것도 하지 않는다. 형식이 틀린 줄이 있으면 넣지 않고 ValueError를 낸다(부분만 넣지 않는다)."""
        if not path.exists():
            return HistoryCounts(runs=0, records=0, judgments=0)
        runs: list[HistoryRun] = []
        records: list[LiveRecord] = []
        judgments: list[JudgeResult] = []
        for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not raw.strip():
                continue
            try:
                line = HistoryLine.model_validate({"line": json.loads(raw)}).line
            except (ValueError, ValidationError) as e:
                raise ValueError(f"{path}:{n} is not a valid history line") from e
            if isinstance(line, HistoryRun):
                runs.append(line)
            elif isinstance(line, HistoryRecord):
                records.append(line.item)
            else:
                judgments.append(line.result)
        counts = await self._repository.insert_history(runs, records, judgments)
        logger.info("history_loaded", path=str(path), **counts.model_dump())
        return counts
