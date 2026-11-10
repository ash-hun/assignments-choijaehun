"""평가 기록 저장소 스냅샷의 줄 형식. 실시간 질의 내역과 대시보드 기준선을 저장소 밖(git)으로 옮겨 다른 환경에서 다시 넣는다."""
from typing import Any, Literal
from pydantic import BaseModel, Field

from app.schema.judge_schema import JudgeResult
from app.schema.eval_schema import LiveRecord


class HistoryRun(BaseModel):
    """Gold Set 실행 하나. manifest는 저장소에 들어 있던 그대로다."""

    kind: Literal["run"] = "run"
    run_id: str
    config_id: str
    manifest: dict[str, Any]


class HistoryRecord(BaseModel):
    """기록 하나와 원래 저장 시각. 시각을 보존해야 최근 질의 순서와 누적 그래프가 원래대로 나온다."""

    kind: Literal["record"] = "record"
    item: LiveRecord


class HistoryJudgment(BaseModel):
    """Judge 호출 결과 하나."""

    kind: Literal["judgment"] = "judgment"
    result: JudgeResult


class HistoryLine(BaseModel):
    """파일 한 줄. kind로 세 형식을 가른다."""

    line: HistoryRun | HistoryRecord | HistoryJudgment = Field(discriminator="kind")


class HistoryCounts(BaseModel):
    """내보내거나 넣은 행 수. 가져오기는 이미 있던 행을 세지 않는다."""

    runs: int
    records: int
    judgments: int
