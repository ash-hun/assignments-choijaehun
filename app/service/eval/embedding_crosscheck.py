"""Embedding 교차 확인. 확정한 Chunking으로 상위 두 모델을 다시 재고, 실험 전에 정한 규칙으로 최종 모델을 판정한다."""
from typing import Literal
from pydantic import BaseModel

from app.service.eval.retrieval_metric import MetricSummary, paired_against
from app.service.eval.chunking_benchmark import ChunkingRun
from app.client.embedding_client import EmbeddingClient
from app.schema.chunk_schema import Chunk

CrosscheckReason = Literal["incumbent_better", "challenger_better", "tied_challenger_coverage_lower", "tied_challenger_cheaper"]


class ModelResult(BaseModel):
    """모델 하나의 언어별 결과와, 모델 최대 입력을 넘어 뒷부분이 잘리는 청크 수."""

    model: str
    max_input_tokens: int
    truncated_chunks: int
    runs: list[ChunkingRun]


class CrosscheckVerdict(BaseModel):
    """기존 선택(incumbent)과 도전 모델(challenger)의 짝지은 차이(incumbent - challenger)와 판정."""

    incumbent: str
    challenger: str
    hit_at_5_diff: dict[str, MetricSummary]
    mrr_diff: dict[str, MetricSummary]
    coverage_at_5: dict[str, dict[str, float]]
    chosen: str
    reason: CrosscheckReason


def truncated_chunks(client: EmbeddingClient, chunks: list[Chunk], max_input_tokens: int) -> int:
    """접두어와 특수 토큰을 붙여 센 길이가 모델 최대 입력을 넘는 청크 수. 넘는 부분은 임베딩에 반영되지 않는다."""
    return sum(1 for c in chunks if client.token_count(c.text) > max_input_tokens)


def judge(incumbent: ModelResult, challenger: ModelResult) -> CrosscheckVerdict:
    """Hit@5 짝지은 차이 구간이 한 언어라도 0을 벗어나면 앞선 쪽. 차이가 없으면 도전 모델의 근거 보존@5가 모든 언어에서
    기존 이상일 때만 비용 규칙으로 도전 모델, 아니면 기존 선택을 유지한다. 언어마다 방향이 엇갈리면 기존 선택이 먼저다.
    """
    pairs = {
        a.language: (a, b)
        for a in incumbent.runs for b in challenger.runs if a.language == b.language
    }
    diffs = {language: paired_against(a.per_question, b.per_question) for language, (a, b) in pairs.items()}
    hit = {language: d["hit_at_5_diff"] for language, d in diffs.items()}
    coverage = {
        language: {incumbent.model: a.evidence_covered_at_5, challenger.model: b.evidence_covered_at_5}
        for language, (a, b) in pairs.items()
    }
    reason: CrosscheckReason
    if any(d.ci_low > 0 for d in hit.values()):
        reason = "incumbent_better"
    elif any(d.ci_high < 0 for d in hit.values()):
        reason = "challenger_better"
    elif all(b.evidence_covered_at_5 >= a.evidence_covered_at_5 for a, b in pairs.values()):
        reason = "tied_challenger_cheaper"
    else:
        reason = "tied_challenger_coverage_lower"
    chosen = challenger.model if reason in ("challenger_better", "tied_challenger_cheaper") else incumbent.model
    return CrosscheckVerdict(
        incumbent=incumbent.model, challenger=challenger.model, hit_at_5_diff=hit,
        mrr_diff={language: d["mrr_diff"] for language, d in diffs.items()}, coverage_at_5=coverage,
        chosen=chosen, reason=reason,
    )
