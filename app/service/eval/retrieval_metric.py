"""근거 단위 검색 지표. 검색된 청크에 Gold 근거 구절이 들어 있는지로 Hit@k, 근거 재현율, MRR을 계산한다."""
from pydantic import BaseModel

from app.service.eval.evidence_matcher import normalize
from app.service.ingest.text_cleaner import clean_text
from app.schema.gold_schema import GoldItem
from app.schema.chunk_schema import Chunk

# 근거 구절에서 잘라낸 60자 창 하나가 청크에 그대로 있으면 그 근거를 찾은 것으로 본다.
# 특정 구절의 60자 원문이 다른 곳에 우연히 있을 가능성은 낮고, 청크 경계에서 끊긴 긴 문장도 잡을 수 있다.
ANCHOR_CHARS = 60
ANCHOR_STRIDE = 30


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
