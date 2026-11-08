"""근거 단위 검색 지표. 검색된 청크에 Gold 근거 구절이 들어 있는지로 Hit@k, 근거 재현율, MRR을 계산하고 bootstrap 구간을 붙인다."""
import math
import random
import statistics
from pydantic import BaseModel

from app.service.eval.evidence_matcher import normalize
from app.service.ingest.text_cleaner import clean_text
from app.schema.eval_schema import RankScore
from app.schema.gold_schema import GoldItem
from app.schema.chunk_schema import Chunk

# 근거 구절에서 잘라낸 60자 창 하나가 청크에 그대로 있으면 그 근거를 찾은 것으로 본다.
# 특정 구절의 60자 원문이 다른 곳에 우연히 있을 가능성은 낮고, 청크 경계에서 끊긴 긴 문장도 잡을 수 있다.
ANCHOR_CHARS = 60
ANCHOR_STRIDE = 30
BOOTSTRAP_SAMPLES = 2000
BOOTSTRAP_SEED = 2026


class RetrievalScore(BaseModel):
    """문항 하나의 검색 결과 판정."""

    item_id: str
    type: str
    first_hit_rank: int | None
    hit_at_5: bool
    hit_at_10: bool
    evidence_recall_at_10: float
    doc_recall_at_5: bool
    reciprocal_rank: float


class MetricSummary(BaseModel):
    """지표 하나의 평균과 문항 bootstrap 95% 신뢰구간."""

    mean: float
    ci_low: float
    ci_high: float


class RetrievalSummary(BaseModel):
    """문항 묶음 하나의 검색 지표 요약."""

    questions: int
    hit_at_5: MetricSummary
    hit_at_10: MetricSummary
    mrr_at_10: MetricSummary
    evidence_recall_at_10: MetricSummary
    doc_recall_at_5: MetricSummary
    by_type_hit_at_5: dict[str, float]


def evidence_anchors(quote: str) -> list[str]:
    """근거 구절을 정제하고 60자 창을 30자 간격으로 자른다. 구절이 60자보다 짧으면 구절 전체 하나다.

    청크 분할은 구절을 경계에서 끊을 수 있어서, 구절 전체가 아니라 일부 창만 들어 있어도 근거를 찾은 것으로 본다.
    """
    cleaned = normalize(clean_text(quote))
    if len(cleaned) <= ANCHOR_CHARS:
        return [cleaned]
    starts = list(range(0, len(cleaned) - ANCHOR_CHARS + 1, ANCHOR_STRIDE))
    if starts[-1] != len(cleaned) - ANCHOR_CHARS:
        starts.append(len(cleaned) - ANCHOR_CHARS)
    return [cleaned[s:s + ANCHOR_CHARS] for s in starts]


def shares_evidence(quote: str, other: str) -> bool:
    """두 근거 구절이 60자 창 하나라도 공유하는지. 짧은 구절이 긴 구절 안에 들어가는 경우도 양쪽으로 본다."""
    a, b = normalize(clean_text(quote)), normalize(clean_text(other))
    return any(anchor in b for anchor in evidence_anchors(quote)) or any(anchor in a for anchor in evidence_anchors(other))


def chunk_has_evidence(chunk: Chunk, doc_id: str, anchors: list[str]) -> bool:
    """같은 문서의 청크이고 anchor 중 하나라도 들어 있으면 근거가 있는 청크다."""
    if chunk.doc_id != doc_id:
        return False
    text = normalize(chunk.text)
    return any(anchor in text for anchor in anchors)


def score(item: GoldItem, ranked: list[Chunk]) -> RetrievalScore:
    """순위가 매겨진 청크 목록(최대 10개)으로 문항 하나를 판정한다. 답 없는 문항은 넣지 않는다."""
    if not item.answerable:
        raise ValueError("retrieval metrics are defined only for answerable items")
    evidence = [(e.doc_id, evidence_anchors(e.quote)) for e in item.evidence]
    matched_ranks = [
        rank for rank, chunk in enumerate(ranked[:10], start=1)
        if any(chunk_has_evidence(chunk, doc, anchors) for doc, anchors in evidence)
    ]
    found = [any(chunk_has_evidence(c, doc, anchors) for c in ranked[:10]) for doc, anchors in evidence]
    first = matched_ranks[0] if matched_ranks else None
    return RetrievalScore(
        item_id=str(item.id),
        type=item.type,
        first_hit_rank=first,
        hit_at_5=first is not None and first <= 5,
        hit_at_10=first is not None,
        evidence_recall_at_10=sum(found) / len(found),
        doc_recall_at_5=bool(set(item.gold_doc_ids) & {c.doc_id for c in ranked[:5]}),
        reciprocal_rank=1 / first if first else 0.0,
    )


def relevant_chunk_ids(item: GoldItem, chunks: list[Chunk]) -> set[str]:
    """인덱스 전체에서 이 문항의 근거 구절이 하나라도 들어 있는 청크 id. nDCG의 이상적 순위를 만들 때 쓴다."""
    evidence = [(e.doc_id, evidence_anchors(e.quote)) for e in item.evidence]
    return {c.chunk_id for c in chunks if any(chunk_has_evidence(c, doc, anchors) for doc, anchors in evidence)}


def rank_score(item: GoldItem, ranked: list[Chunk], relevant_ids: set[str]) -> RankScore:
    """순위가 매겨진 청크 목록(최대 10개)의 Recall@k, Precision@k, F1@k(k는 5, 10), 역순위, nDCG@10.

    Recall은 근거 구절 단위(찾은 구절 / 전체 구절), Precision은 청크 단위(관련 청크 / k)다.
    """
    if not item.answerable:
        raise ValueError("retrieval metrics are defined only for answerable items")
    top = ranked[:10]
    evidence = [(e.doc_id, evidence_anchors(e.quote)) for e in item.evidence]
    relevant = [any(chunk_has_evidence(c, doc, anchors) for doc, anchors in evidence) for c in top]

    def recall(k: int) -> float:
        found = [any(chunk_has_evidence(c, doc, anchors) for c in top[:k]) for doc, anchors in evidence]
        return sum(found) / len(found)

    def precision(k: int) -> float:
        return sum(relevant[:k]) / k

    first = next((rank for rank, hit in enumerate(relevant, start=1) if hit), None)
    dcg = sum(1 / math.log2(rank + 1) for rank, hit in enumerate(relevant, start=1) if hit)
    ideal = sum(1 / math.log2(rank + 1) for rank in range(1, min(len(relevant_ids), 10) + 1))
    r5, r10, p5, p10 = recall(5), recall(10), precision(5), precision(10)
    return RankScore(
        recall_at_5=round(r5, 4), recall_at_10=round(r10, 4), precision_at_5=round(p5, 4), precision_at_10=round(p10, 4),
        f1_at_5=round(_f1(p5, r5), 4), f1_at_10=round(_f1(p10, r10), 4),
        reciprocal_rank=round(1 / first, 4) if first else 0.0, ndcg_at_10=round(dcg / ideal, 4) if ideal else 0.0,
    )


def _f1(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def summarize(scores: list[RetrievalScore]) -> RetrievalSummary:
    """문항별 판정을 지표별 평균과 구간, 유형별 Hit@5로 묶는다."""
    by_type: dict[str, list[float]] = {}
    for s in scores:
        by_type.setdefault(s.type, []).append(float(s.hit_at_5))
    return RetrievalSummary(
        questions=len(scores),
        hit_at_5=bootstrap([float(s.hit_at_5) for s in scores]),
        hit_at_10=bootstrap([float(s.hit_at_10) for s in scores]),
        mrr_at_10=bootstrap([s.reciprocal_rank for s in scores]),
        evidence_recall_at_10=bootstrap([s.evidence_recall_at_10 for s in scores]),
        doc_recall_at_5=bootstrap([float(s.doc_recall_at_5) for s in scores]),
        by_type_hit_at_5={t: round(statistics.fmean(v), 4) for t, v in sorted(by_type.items())},
    )


def bootstrap(values: list[float]) -> MetricSummary:
    """문항을 복원 추출해 평균의 95% 구간을 구한다. seed가 고정이라 같은 입력이면 같은 구간이다."""
    rng = random.Random(BOOTSTRAP_SEED)
    means = sorted(statistics.fmean(rng.choices(values, k=len(values))) for _ in range(BOOTSTRAP_SAMPLES))
    return MetricSummary(
        mean=round(statistics.fmean(values), 4),
        ci_low=round(means[int(0.025 * BOOTSTRAP_SAMPLES)], 4),
        ci_high=round(means[int(0.975 * BOOTSTRAP_SAMPLES) - 1], 4),
    )


def paired_difference(a: list[float], b: list[float]) -> MetricSummary:
    """같은 문항에 대한 두 설정 점수 차(a - b)의 평균과 95% 구간. 구간이 0을 포함하면 차이 없음으로 본다."""
    return bootstrap([x - y for x, y in zip(a, b)])


def paired_against(best: list[RetrievalScore], other: list[RetrievalScore]) -> dict[str, MetricSummary]:
    """같은 문항 순서의 두 판정 목록으로 Hit@5와 MRR의 짝지은 차이(best - other)를 구한다."""
    return {
        "hit_at_5_diff": paired_difference([float(s.hit_at_5) for s in best], [float(s.hit_at_5) for s in other]),
        "mrr_diff": paired_difference([s.reciprocal_rank for s in best], [s.reciprocal_rank for s in other]),
    }
