"""Judge 신뢰성 계산. 표본 간 일치는 eval_summarizer가, 사람 라벨 대비 일치율과 Cohen's kappa는 이 모듈이 낸다."""
from pydantic import BaseModel
from collections import Counter

from app.schema.judge_schema import QUALITY_JUDGE_ITEMS, HumanLabel, JudgeResult, RubricVerdict
from app.service.eval.judge_metric import majority_bool, majority_verdict

KAPPA_TARGET = 0.60


class AgreementRow(BaseModel):
    """판정 항목 하나의 사람 라벨 대비 일치. kappa는 한쪽이 한 범주만 쓰면 정의되지 않아 None이다."""

    item: str
    pairs: int
    agreement: float
    kappa: float | None
    passed: bool | None


def cohen_kappa(a: list[str], b: list[str]) -> float | None:
    """두 판정자의 범주 일치에서 우연 일치를 뺀 값. 기대 일치가 1이면(둘 다 한 범주) 정의되지 않는다."""
    n = len(a)
    if n == 0:
        return None
    observed = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    expected = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return None if expected == 1 else round((observed - expected) / (1 - expected), 4)


def compare(labels: list[HumanLabel], judged: dict[str, list[JudgeResult]]) -> list[AgreementRow]:
    """라벨을 다 채운 기록만, Judge 표본 다수결과 항목별로 비교한다. 요점과 인용은 요점, 인용 하나가 한 쌍이다."""
    pairs: dict[str, tuple[list[str], list[str]]] = {name: ([], []) for name in
                                                      ["citation", "key_point", "rejection", "accuracy", *QUALITY_JUDGE_ITEMS]}
    for label in labels:
        results = judged.get(label.record_id, [])
        rubrics = [r.rubric for r in results if r.kind == "rubric" and r.ok and r.rubric is not None]
        citations = [r.citations for r in results if r.kind == "citation" and r.ok and r.citations is not None]
        if not label.complete() or not rubrics:
            continue
        human_points = [bool(v) for v in label.key_points]
        human_rejections = [bool(v) for v in label.rejections]
        judge_points = [majority_bool([r.key_points[i] for r in rubrics]) for i in range(len(human_points))]
        judge_rejections = [majority_bool([r.rejections[i] for r in rubrics]) for i in range(len(human_rejections))]
        _extend(pairs["key_point"], human_points, judge_points)
        _extend(pairs["rejection"], human_rejections, judge_rejections)
        if label.key_points:
            _extend(pairs["accuracy"], [all(human_points) and not any(human_rejections)],
                    [all(judge_points) and not any(judge_rejections)])
        if citations and len(citations[0]) == len(label.citations):
            _extend(pairs["citation"], [bool(v) for v in label.citations],
                    [majority_bool([c[i] for c in citations]) for i in range(len(label.citations))])
        for item in QUALITY_JUDGE_ITEMS:
            human: RubricVerdict | None = getattr(label, item)
            if human is not None:
                pairs[item][0].append(human)
                pairs[item][1].append(majority_verdict([getattr(r, item) for r in rubrics]))
    rows = []
    for name, (human_values, judge_values) in pairs.items():
        n = len(human_values)
        kappa = cohen_kappa(human_values, judge_values)
        rows.append(AgreementRow(
            item=name, pairs=n, agreement=round(sum(x == y for x, y in zip(human_values, judge_values)) / n, 4) if n else 0.0,
            kappa=kappa, passed=None if kappa is None else kappa >= KAPPA_TARGET,
        ))
    return rows


def _extend(target: tuple[list[str], list[str]], human: list[bool], judge: list[bool]) -> None:
    target[0].extend(str(v) for v in human)
    target[1].extend(str(v) for v in judge)
