"""평가 Report 파일을 쓴다. 생성 시각을 넣지 않아 같은 기록이면 다시 써도 diff가 없다."""
import json
from pathlib import Path

from app.service.eval.eval_summarizer import LatencySummary, LanguageSummary
from app.service.eval.retrieval_metric import MetricSummary
from app.schema.eval_schema import EvalRecord, EvalManifest

RETRIEVAL_LABELS = {
    "recall_at_5": "Recall@5", "recall_at_10": "Recall@10", "precision_at_5": "Precision@5",
    "precision_at_10": "Precision@10", "f1_at_5": "F1@5", "f1_at_10": "F1@10", "reciprocal_rank": "MRR@10",
    "ndcg_at_10": "nDCG@10",
}


def write_report(
    out: Path, run_id: str, manifest: EvalManifest, records: list[EvalRecord], summaries: list[LanguageSummary],
    failed: list[str],
) -> None:
    """`out/<run_id>/`에 manifest.json, results.jsonl, summary.json, summary.md를 쓴다. failed는 기록하지 못한 문항 id다."""
    target = out / run_id
    target.mkdir(parents=True, exist_ok=True)
    (target / "manifest.json").write_text(_json(manifest.model_dump(mode="json")), encoding="utf-8")
    (target / "results.jsonl").write_text("".join(r.model_dump_json() + "\n" for r in records), encoding="utf-8")
    summary = {"failed_items": failed, "languages": [s.model_dump(mode="json") for s in summaries]}
    (target / "summary.json").write_text(_json(summary), encoding="utf-8")
    (target / "summary.md").write_text(render_markdown(run_id, manifest, summaries, failed), encoding="utf-8")


def render_markdown(run_id: str, manifest: EvalManifest, summaries: list[LanguageSummary], failed: list[str]) -> str:
    """언어별 검색, 거절, 생성 규칙 지표, 운영 지표 표. 구간은 문항 bootstrap 95%다. 실패 문항은 지표에서 빠진다."""
    lines = [
        f"# 평가 Report: {run_id}", "",
        f"- 설정: `{manifest.config.name}`, config_id `{manifest.config_id}`, git `{manifest.git_commit}`",
        f"- 인덱스: `{manifest.collection}`, 답변 모델 `{manifest.answer_model}`, 거절 임계값 {manifest.refusal_threshold}",
        f"- 근거 수 top_k {manifest.config.top_k}, 검색 지표 깊이 {manifest.config.retrieval_depth}",
        f"- 기록하지 못한 문항 {len(failed)}개" + (": " + ", ".join(f"`{i}`" for i in failed) if failed else ""), "",
        "## 검색", "",
        "| 지표 | " + " | ".join(s.language for s in summaries) + " |",
        "|---|" + "---|" * len(summaries),
    ]
    for key, label in RETRIEVAL_LABELS.items():
        lines.append(f"| {label} | " + " | ".join(_ci(s.retrieval.get(key)) for s in summaries) + " |")
    lines.append("| 검색 최고 점수 중앙값 | " + " | ".join(_num(s.top_score_median) for s in summaries) + " |")
    lines.append("| 임계값 ±0.05 구간 비율 | " + " | ".join(f"{s.near_threshold_rate:.3f}" for s in summaries) + " |")
    lines += ["", "유형별 Recall@5 / nDCG@10:", ""]
    for s in summaries:
        cells = ", ".join(f"{t} {v['recall_at_5']:.3f} / {v['ndcg_at_10']:.3f}" for t, v in s.retrieval_by_type.items())
        lines.append(f"- {s.language}: {cells}")
    lines += [
        "", "## 거절과 인용 규칙", "",
        "| 지표 | " + " | ".join(s.language for s in summaries) + " |",
        "|---|" + "---|" * len(summaries),
        "| 답 없는 문항 거절률 | " + " | ".join(_ci(s.unanswerable_refusal) for s in summaries) + " |",
        "| 답 있는 문항 오거절률 | " + " | ".join(_ci(s.answerable_false_refusal) for s in summaries) + " |",
        "| 단계별 거절 수 | " + " | ".join(_stages(s.refusals_by_stage) for s in summaries) + " |",
        "| 지운 인용 없음(답한 문항) | " + " | ".join(_ci(s.no_dropped_citation_rate) for s in summaries) + " |",
        "", "## 운영(밀리초, 중앙값 / p95)", "",
        "| 지표 | " + " | ".join(s.language for s in summaries) + " |",
        "|---|" + "---|" * len(summaries),
        "| 검색 지연 | " + " | ".join(_lat(s.retrieval_ms) for s in summaries) + " |",
        "| TTFT | " + " | ".join(_lat(s.ttft_ms) for s in summaries) + " |",
        "| TPOT | " + " | ".join(_lat(s.tpot_ms) for s in summaries) + " |",
        "| Latency(답한 문항) | " + " | ".join(_lat(s.latency_ms) for s in summaries) + " |",
        "| Latency(거절 문항) | " + " | ".join(_lat(s.refused_latency_ms) for s in summaries) + " |",
        "| 문항당 비용(원) | " + " | ".join(f"{s.cost_krw_per_item:.3f}" for s in summaries) + " |",
        "| 전체 비용(원) | " + " | ".join(f"{s.cost_krw_total:.2f}" for s in summaries) + " |",
        "",
    ]
    return "\n".join(lines)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _ci(m: MetricSummary | None) -> str:
    return f"{m.mean:.3f} [{m.ci_low:.3f}, {m.ci_high:.3f}]" if m else "-"


def _num(v: float | None) -> str:
    return f"{v:.4f}" if v is not None else "-"


def _lat(s: LatencySummary) -> str:
    return f"{s.median:.0f} / {s.p95:.0f} (n={s.count})" if s.median is not None and s.p95 is not None else "-"


def _stages(stages: dict[str, int]) -> str:
    return ", ".join(f"{k} {v}" for k, v in stages.items()) or "0"
