"""Gold Set 평가 실행의 설정, 기록, 요약 모델. 같은 모델이 평가 기록 저장소와 Report 파일에 쓰인다."""
import json
import hashlib
from typing import Literal
from pydantic import BaseModel, Field

from app.schema.query_schema import QueryStatus

EvalSource = Literal["gold", "live"]
# 지표 타당성 검증용 변형(research/gold_metric_selection.md의 "지표 타당성 검증"). none이 실제 서비스 구성이다.
EvalVariant = Literal["none", "random_chunks", "no_refusal", "shuffled_citations", "swapped_context"]


class EvalConfig(BaseModel):
    """`configs/*.toml` 하나. 파이프라인 구성(임베딩, Chunk, 임계값, 답변 모델)은 환경 설정에서 오고 manifest에 기록된다."""

    name: str = Field(min_length=1, pattern=r"^[a-z0-9_-]+$")
    gold_files: list[str] = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    retrieval_depth: int = Field(default=10, ge=1, le=50)
    concurrency: int = Field(default=4, ge=1, le=16)
    variant: EvalVariant = "none"
    # 답마다 Judge를 몇 번 부를지. 0이면 Judge를 부르지 않는다. Gold Set 평가는 3회 다수결이다.
    judge_samples: int = Field(default=3, ge=0, le=5)


class EvalManifest(BaseModel):
    """실행을 재현하는 데 필요한 값. run_id는 git commit을 뺀 나머지의 해시라, 코드만 바뀌고 결과에 영향이 없으면 같은 실행으로 이어 쓴다."""

    config: EvalConfig
    config_id: str
    gold_hashes: dict[str, str]
    corpus_manifest_hash: str
    index_contract: dict[str, str]
    collection: str
    answer_model: str
    answer_temperature: float | None
    answer_seed: int | None
    answer_max_tokens: int
    refusal_threshold: float
    prompt_hash: str
    bootstrap_seed: int
    git_commit: str

    def run_id(self) -> str:
        """config 이름과 git commit을 뺀 값의 해시 앞 12자리를 붙인다. 같은 입력이면 같은 run_id다.

        Judge 표본 수는 생성 기록을 바꾸지 않아 빼고, 변형이 없으면(none) 변형 필드도 빼서 기존 실행의 run_id를 유지한다.
        """
        body = self.model_dump(exclude={"git_commit"})
        body["config"].pop("judge_samples")
        if self.config.variant == "none":
            body["config"].pop("variant")
        digest = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
        return f"{self.config.name}-{digest}"


class RankScore(BaseModel):
    """답 있는 문항 하나의 순위 기반 검색 지표. 관련 청크는 근거 구절의 60자 창이 들어 있는 같은 문서의 청크다."""

    recall_at_5: float
    recall_at_10: float
    precision_at_5: float
    precision_at_10: float
    f1_at_5: float
    f1_at_10: float
    reciprocal_rank: float
    ndcg_at_10: float


class EvalRecord(BaseModel):
    """질의 하나의 실행 결과. Gold Set 평가와 실시간 질의가 같은 모양으로 저장된다."""

    record_id: str
    run_id: str | None
    source: EvalSource
    config_id: str
    item_id: str | None
    language: str | None
    type: str | None
    answerable: bool | None
    question: str
    status: QueryStatus
    refusal_stage: Literal["retrieval", "generation"] | None
    answer: str
    cited_chunk_ids: list[str]
    dropped_citations: int
    retrieved_chunk_ids: list[str]
    retrieval_scores: list[float]
    top_score: float | None
    rank: RankScore | None
    retrieval_ms: int | None
    first_token_ms: int | None
    latency_ms: int
    input_tokens: int
    output_tokens: int
    cost_krw: float
