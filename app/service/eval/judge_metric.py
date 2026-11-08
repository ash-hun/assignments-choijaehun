"""Judge 지표 계산. 답을 (문장, 인용 번호) 쌍으로 나누고, Judge 출력을 검증하고, 여러 표본을 다수결로 묶어 기록별 판정을 만든다."""
import re
import statistics
from typing import Any
from collections import Counter

from app.schema.judge_schema import ALWAYS_APPLICABLE, QUALITY_JUDGE_ITEMS, JudgeResult, RubricVerdict, RubricJudgment, RecordJudgment
from app.schema.eval_schema import EvalRecord

CITATION = re.compile(r"\[(\d+)\]")
CODE_SPAN = re.compile(r"`[^`]*`")
SENTENCE_END = re.compile(r"(?<=[.!?。])\s+")
# 동률이면 보수적으로 실패 쪽을 고른다. 표본 수가 짝수거나 세 판정이 모두 다를 때만 쓰인다.
TIE_ORDER: list[RubricVerdict] = ["fail", "pass", "na"]
DROPPED_ITEM = "no_dropped_citation"


def citation_pairs(answer: str) -> list[tuple[str, int]]:
    """줄과 문장 끝으로 나눈 문장마다 인용 번호를 한 번씩 뽑는다. 코드 span 안의 [n]은 인용이 아니다."""
    pairs: list[tuple[str, int]] = []
    for line in answer.splitlines():
        for sentence in SENTENCE_END.split(line.strip()):
            refs = dict.fromkeys(int(n) for n in CITATION.findall(CODE_SPAN.sub("", sentence)))
            pairs += [(sentence, ref) for ref in refs]
    return pairs


def parse_citations(raw: dict[str, Any], count: int) -> list[bool] | None:
    """id가 0부터 count-1까지 정확히 한 번씩 있어야 한다. 아니면 None(판정 실패)."""
    judged = {j["id"]: bool(j["supported"]) for j in raw.get("judgments", [])}
    if sorted(judged) != list(range(count)):
        return None
    return [judged[i] for i in range(count)]


def parse_rubric(raw: dict[str, Any], key_points: int, rejections: int) -> RubricJudgment | None:
    """기준 수와 목록 길이가 맞지 않거나, 해당 없음을 고를 수 없는 항목에 na가 오면 None(판정 실패)."""
    try:
        judgment = RubricJudgment.model_validate(raw)
    except ValueError:
        return None
    if len(judgment.key_points) != key_points or len(judgment.rejections) != rejections:
        return None
    if any(getattr(judgment, item) == "na" for item in ALWAYS_APPLICABLE):
        return None
    return judgment


def aggregate(record: EvalRecord, results: list[JudgeResult], has_criteria: bool) -> RecordJudgment:
    """성공한 표본만 다수결로 묶는다. 루브릭 표본이 하나도 없으면 failed다."""
    citations = [r.citations for r in results if r.kind == "citation" and r.ok and r.citations is not None]
    rubrics = [r.rubric for r in results if r.kind == "rubric" and r.ok and r.rubric is not None]
    agreement: dict[str, bool] = {}
    precision = None
    if citations and citations[0]:
        claims = [majority_bool([c[i] for c in citations]) for i in range(len(citations[0]))]
        precision = round(sum(claims) / len(claims), 4)
        if len(citations) > 1:
            agreement["citation_precision"] = all(c == citations[0] for c in citations)
    items: dict[str, bool | None] = {DROPPED_ITEM: record.dropped_citations == 0}
    accuracy = key_point_rate = None
    if rubrics:
        verdicts = {item: majority_verdict([getattr(r, item) for r in rubrics]) for item in QUALITY_JUDGE_ITEMS}
        items.update({item: None if v == "na" else v == "pass" for item, v in verdicts.items()})
        if has_criteria:
            points = [majority_bool([r.key_points[i] for r in rubrics]) for i in range(len(rubrics[0].key_points))]
            stated = [majority_bool([r.rejections[i] for r in rubrics]) for i in range(len(rubrics[0].rejections))]
            accuracy = all(points) and not any(stated)
            key_point_rate = round(sum(points) / len(points), 4) if points else None
        if len(rubrics) > 1:
            agreement.update({item: len({getattr(r, item) for r in rubrics}) == 1 for item in QUALITY_JUDGE_ITEMS})
            if has_criteria:
                agreement["accuracy"] = len({all(r.key_points) and not any(r.rejections) for r in rubrics}) == 1
    applicable = [v for v in items.values() if v is not None]
    return RecordJudgment(
        record_id=record.record_id, samples=len(rubrics), citation_precision=precision, accuracy=accuracy,
        key_point_rate=key_point_rate, quality_items=items,
        quality_score=round(statistics.fmean(applicable), 4) if rubrics and applicable else None,
        agreement=agreement, failed=not rubrics,
    )


def majority_bool(values: list[bool]) -> bool:
    # 동률이면 False다. Gold Set 평가는 표본 3개라 동률이 없고, 표본이 짝수일 때만 쓰인다.
    return sum(values) * 2 > len(values)


def majority_verdict(values: list[RubricVerdict]) -> RubricVerdict:
    counts = Counter(values)
    return min(counts, key=lambda v: (-counts[v], TIE_ORDER.index(v)))
