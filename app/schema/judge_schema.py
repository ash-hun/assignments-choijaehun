"""Judge 판정 모델. 호출 한 번의 원판정과, 여러 번의 판정을 다수결로 묶은 기록별 판정을 함께 정의한다."""
from typing import Literal
from pydantic import BaseModel

RubricVerdict = Literal["pass", "fail", "na"]
JudgeKind = Literal["citation", "rubric"]
JUDGE_KINDS: list[JudgeKind] = ["citation", "rubric"]
# uv 답변 품질 점수의 Judge 항목. research/gold_metric_selection.md의 루브릭 v1 순서다.
QUALITY_JUDGE_ITEMS = ["unsupported_claim", "identifier_accuracy", "interface_separation", "version_status", "prior_knowledge"]
# 품질 점수에 넣는 항목. 루브릭 v1 6항목 중 검증 조건(반응성, 변별력, 신뢰성, 중복성)을 모두 통과한 항목만 둔다.
# 5항목은 기준선 통과율이 1.000이라 변별력에서, "근거 없는 주장 없음"은 3회 판정 일치율(0.839, 0.821)이 0.90에 못 미쳐
# 신뢰성에서 빠졌다. 채택 항목이 없어 품질 점수는 비고, 항목별 통과율만 참고값으로 보고한다
# (research/gold_metric_selection.md의 "품질 점수와 Citation Precision 구성 확정").
QUALITY_SCORE_ITEMS: list[str] = []
# 해당 없음을 고를 수 없는 항목. 이 항목에 na가 오면 판정 실패로 본다.
ALWAYS_APPLICABLE = {"unsupported_claim", "prior_knowledge"}


class RubricJudgment(BaseModel):
    """루브릭 호출 한 번의 판정. key_points, rejections는 기준 순서대로이고 정답 기준이 없으면 빈 목록이다."""

    key_points: list[bool]
    rejections: list[bool]
    unsupported_claim: RubricVerdict
    identifier_accuracy: RubricVerdict
    interface_separation: RubricVerdict
    version_status: RubricVerdict
    prior_knowledge: RubricVerdict
    reason: str


class JudgeResult(BaseModel):
    """Judge 호출 한 번의 결과. ok가 False면 출력이 스키마나 규칙을 어겨 집계에서 빠진다."""

    record_id: str
    kind: JudgeKind
    sample: int
    judge_model: str
    prompt_version: str
    ok: bool
    citations: list[bool] | None = None
    rubric: RubricJudgment | None = None
    input_tokens: int
    output_tokens: int


class RecordJudgment(BaseModel):
    """기록 하나의 판정을 표본 다수결로 묶은 값. None은 해당 없음이나 판정 실패다.

    agreement는 항목마다 모든 표본의 판정이 같았는지다. 표본이 하나면 비어 있다.
    """

    record_id: str
    samples: int
    citation_precision: float | None
    accuracy: bool | None
    key_point_rate: float | None
    quality_items: dict[str, bool | None]
    quality_score: float | None
    agreement: dict[str, bool]
    failed: bool


class HumanLabel(BaseModel):
    """사람이 같은 루브릭으로 매긴 판정. 비어 있는(None) 값은 아직 라벨링하지 않은 것이다."""

    record_id: str
    item_id: str
    language: str
    type: str
    citations: list[bool | None]
    key_points: list[bool | None]
    rejections: list[bool | None]
    unsupported_claim: RubricVerdict | None = None
    identifier_accuracy: RubricVerdict | None = None
    interface_separation: RubricVerdict | None = None
    version_status: RubricVerdict | None = None
    prior_knowledge: RubricVerdict | None = None
    note: str = ""

    def complete(self) -> bool:
        """모든 칸을 채웠는지."""
        lists = [*self.citations, *self.key_points, *self.rejections]
        return all(v is not None for v in lists) and all(getattr(self, item) is not None for item in QUALITY_JUDGE_ITEMS)
