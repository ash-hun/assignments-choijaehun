"""Part C 검색 방식 비교 명령. compare: 네 조건의 test set 기록을 짝지어 판정, dev-check: dev set 검색 지표로 언어별 선택을 확인."""
import sys
import json
import asyncio
import argparse
import statistics
from pathlib import Path

from app.service.eval.fusion_comparator import METRICS, ItemValues, item_values, paired_diff, group_means, retrieval_refusals
from app.service.eval.retrieval_metric import rank_score, relevant_chunk_ids
from app.service.query.query_builder import open_query_service
from app.cli.judge_check_cli import load_run, judgments_of
from app.common.settings import Settings, get_settings
from app.schema.query_schema import RetrievalMode
from app.schema.eval_schema import EvalConfig
from app.schema.eval_schema import EvalRecord
from app.cli.eval_run_cli import load_items
from app.common.logger import get_logger

# project_planning/experiments/12_hybrid_fusion.md의 조건과 비교 쌍. 네 쌍이라 Bonferroni로 98.75% 구간을 쓴다.
CONDITIONS = {"dense": "configs/baseline.toml", "bm25": "configs/fusion_bm25.toml", "rrf": "configs/fusion_rrf.toml",
              "cc": "configs/fusion_cc.toml"}
COMPARISONS = [("bm25", "dense"), ("rrf", "dense"), ("cc", "dense"), ("cc", "rrf")]
LEVEL = 1 - 0.05 / len(COMPARISONS)
GROUP_METRICS = ["recall_at_5", "ndcg_at_10", "accuracy", "answerable_refused"]
OUT = "artifacts/hybrid_fusion/results.json"
# 언어별 선택(routed)은 test set 결과를 보고 정했다. 그 결정에 쓰지 않은 dev set으로 검색 지표만 확인한다(LLM 호출 없음).
DEV_FILES = ["data/gold/dev_set.jsonl", "data/gold/dev_set_ko.jsonl"]
DEV_MODES: list[RetrievalMode] = ["dense", "cc", "routed"]
DEV_OUT = "artifacts/hybrid_fusion/dev_check.json"

logger = get_logger(__name__)


async def compare(settings: Settings) -> dict[str, object]:
    """조건마다 기록과 Judge 3회 다수결을 읽어 문항 값을 만들고, 비교 쌍마다 모든 지표의 짝지은 차이를 낸다."""
    items: dict[str, list[ItemValues]] = {}
    records: dict[str, list[EvalRecord]] = {}
    for name, path in CONDITIONS.items():
        rows, grouped, gold = await load_run(settings, path, None)
        judged = judgments_of(rows, grouped, gold)
        records[name] = rows
        items[name] = [item_values(r, judged.get(r.record_id)) for r in rows]
    gate = retrieval_refusals(records["dense"])
    return {
        "level": LEVEL,
        "comparisons": [paired_diff(a, items[a], b, items[b], m, LEVEL).model_dump() for a, b in COMPARISONS for m in METRICS],
        "groups": [g.model_dump() for name in CONDITIONS for m in GROUP_METRICS for g in group_means(name, items[name], m)],
        "same_retrieval_refusals": {name: retrieval_refusals(rows) == gate for name, rows in records.items()},
        "operations": {name: operations(rows, settings.answer_max_tokens) for name, rows in records.items()},
    }


async def dev_check(settings: Settings) -> dict[str, object]:
    """dev set 답 있는 문항을 세 방식으로 검색해 Recall@5, nDCG@10을 매기고, Dense 대비 짝지은 차이(95%)를 언어별로 낸다."""
    items, _ = load_items(EvalConfig(name="dev-check", gold_files=DEV_FILES, judge_samples=0))
    answerable = [i for i in items if i.answerable]
    values: dict[str, list[ItemValues]] = {}
    for mode in DEV_MODES:
        async with open_query_service(settings.model_copy(update={"retrieval_mode": mode})) as parts:
            chunks = await parts.repository.all_chunks(parts.collection)
            rows = []
            for item in answerable:
                ranked = [h.chunk for h in (await parts.retriever.retrieve(item.question, 10)).hits]
                rank = rank_score(item, ranked, relevant_chunk_ids(item, chunks))
                rows.append(ItemValues(key=(str(item.id), item.language), type=item.type,
                                       values={"recall_at_5": rank.recall_at_5, "ndcg_at_10": rank.ndcg_at_10}))
            values[mode] = rows
    diffs = []
    for language in ("en", "ko", "all"):
        subset = {m: [v for v in rows if language == "all" or v.key[1] == language] for m, rows in values.items()}
        for a in ("cc", "routed"):
            for metric in ("recall_at_5", "ndcg_at_10"):
                diffs.append({"language": language, **paired_diff(a, subset[a], "dense", subset["dense"], metric, 0.95).model_dump()})
    means = [g.model_dump() for m in DEV_MODES for metric in ("recall_at_5", "ndcg_at_10") for g in group_means(m, values[m], metric)]
    return {"files": DEV_FILES, "comparisons": diffs, "groups": means}


def operations(records: list[EvalRecord], max_tokens: int) -> dict[str, float | int | None]:
    """검색 지연, 답한 질의의 전체 지연, 질의당 비용, 답한 수, 출력 상한에 닿은 답 수."""
    answered = [r for r in records if r.status == "answered"]
    retrieval = [float(r.retrieval_ms) for r in records if r.retrieval_ms is not None]
    latency = [float(r.latency_ms) for r in answered]
    return {
        "records": len(records), "answered": len(answered),
        "retrieval_ms_p50": _quantile(retrieval, 0.5), "retrieval_ms_p95": _quantile(retrieval, 0.95),
        "latency_ms_p50": _quantile(latency, 0.5), "latency_ms_p95": _quantile(latency, 0.95),
        "cost_krw_mean": round(statistics.fmean(r.cost_krw for r in records), 4) if records else None,
        "truncated": sum(r.output_tokens >= max_tokens for r in answered),
    }


def _quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


def main(argv: list[str] | None = None) -> int:
    """compare는 기록이 없는 조건이 있으면 그 조건의 make eval 명령을 알려 주고 멈춘다. 두 명령 모두 LLM을 새로 부르지 않는다."""
    parser = argparse.ArgumentParser(prog="fusion-compare")
    parser.add_argument("command", nargs="?", choices=["compare", "dev-check"], default="compare")
    args = parser.parse_args(argv)
    settings = get_settings()
    if args.command == "dev-check":
        _write(settings.research_dir / DEV_OUT, asyncio.run(dev_check(settings)))
        logger.info("fusion_dev_checked", path=str(settings.research_dir / DEV_OUT))
        return 0
    result = asyncio.run(compare(settings))
    _write(settings.research_dir / OUT, result)
    logger.info("fusion_compared", path=str(settings.research_dir / OUT), same_retrieval_refusals=result["same_retrieval_refusals"])
    return 0


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
