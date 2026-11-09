"""Judge 신뢰성 점검 명령. validity: 망가뜨린 변형 대비 지표 하락, label-sheet: 사람 라벨 시트, agreement: 사람 라벨 대비 kappa."""
import sys
import json
import random
import asyncio
import argparse
from pathlib import Path
from psycopg import AsyncConnection

from app.schema.judge_schema import JUDGE_KINDS, HumanLabel, JudgeResult, RecordJudgment
from app.service.eval.validity_checker import VariantCheck, item_values, check_variant
from app.cli.eval_run_cli import load_items, load_config, build_manifest
from app.service.eval.agreement_calculator import AgreementRow, compare
from app.repository.eval_record_repository import EvalRecordRepository
from app.service.eval.judge_metric import aggregate, citation_pairs
from app.service.query.query_builder import open_query_service
from app.service.eval.judge_prompt import prompt_version
from app.common.settings import Settings, get_settings
from app.schema.eval_schema import EvalRecord
from app.schema.gold_schema import GoldItem
from app.common.logger import get_logger

VALIDITY_CONFIGS = ["configs/validity_random_chunks.toml", "configs/validity_no_refusal.toml",
                    "configs/validity_shuffled_citations.toml", "configs/validity_swapped_context.toml",
                    "configs/validity_stripped_citations.toml"]
VALIDITY_OUT = "artifacts/judge_validity"
AGREEMENT_OUT = "artifacts/judge_agreement"
LABEL_COUNT = 20
LABEL_SEED = 2026
LABELS_PATH = "gold/human_labels.jsonl"
SHEET_PATH = "gold/human_labels_sheet.md"

logger = get_logger(__name__)


async def load_run(
    settings: Settings, config_path: str, max_samples: int | None,
) -> tuple[list[EvalRecord], dict[str, list[JudgeResult]], dict[str, GoldItem]]:
    """설정 하나의 기록과, 현재 Judge 모델과 프롬프트 버전의 판정(앞 max_samples개 표본)을 저장소에서 읽는다."""
    if settings.eval_db_password is None:
        raise SystemExit("EVAL_DB_PASSWORD must be set")
    config = load_config(Path(config_path))
    items, hashes = load_items(config)
    run_id = build_manifest(settings, config, hashes).run_id()
    versions = {kind: prompt_version(kind) for kind in JUDGE_KINDS}
    async with await AsyncConnection.connect(
        host=settings.eval_db_host, port=settings.eval_db_port, dbname=settings.eval_db_name, user=settings.eval_db_user,
        password=settings.eval_db_password.get_secret_value(), autocommit=True, connect_timeout=10,
    ) as conn:
        repository = EvalRecordRepository(conn)
        records = await repository.records(run_id)
        results = await repository.judgments(run_id)
    grouped: dict[str, list[JudgeResult]] = {}
    for r in results:
        if r.judge_model == settings.judge_llm_model and r.prompt_version == versions[r.kind] and (max_samples is None or r.sample < max_samples):
            grouped.setdefault(r.record_id, []).append(r)
    if not records:
        raise SystemExit(f"no records for {run_id}: run `make eval CONFIG={config_path}` first")
    return records, grouped, {str(i.id): i for i in items}


def judgments_of(records: list[EvalRecord], grouped: dict[str, list[JudgeResult]], items: dict[str, GoldItem]) -> dict[str, RecordJudgment]:
    """판정이 있는 답한 기록만 다수결로 묶는다."""
    return {
        r.record_id: aggregate(r, grouped[r.record_id], bool(items.get(r.item_id or "") and items[r.item_id or ""].acceptance_criteria))
        for r in records if r.status == "answered" and r.record_id in grouped
    }


async def validity(settings: Settings) -> list[VariantCheck]:
    """기준선의 첫 표본과 변형의 첫 표본을 같은 영어 문항끼리 비교한다(변형은 Judge 1회라 표본 수를 맞춘다)."""
    records, grouped, items = await load_run(settings, "configs/baseline.toml", 1)
    judged = judgments_of(records, grouped, items)
    baseline = {r.item_id or "": item_values(r, judged.get(r.record_id)) for r in records if r.language == "en"}
    checks = []
    for path in VALIDITY_CONFIGS:
        config = load_config(Path(path))
        v_records, v_grouped, v_items = await load_run(settings, path, 1)
        v_judged = judgments_of(v_records, v_grouped, v_items)
        broken = {r.item_id or "": item_values(r, v_judged.get(r.record_id)) for r in v_records}
        checks.append(check_variant(config.variant, baseline, broken))
    return checks


async def label_sheet(settings: Settings) -> tuple[Path, Path]:
    """판정이 있는 기준선 답 20개를 유형을 돌아가며 고르고, 읽을 시트와 채울 라벨 파일을 쓴다. 라벨 파일이 있으면 덮어쓰지 않는다."""
    records, grouped, items = await load_run(settings, "configs/baseline.toml", None)
    pool = [r for r in records if r.status == "answered" and r.record_id in grouped]
    random.Random(LABEL_SEED).shuffle(pool)
    by_type: dict[str, list[EvalRecord]] = {}
    for r in pool:
        by_type.setdefault(r.type or "", []).append(r)
    chosen: list[EvalRecord] = []
    while len(chosen) < LABEL_COUNT and any(by_type.values()):
        for t in sorted(by_type):
            if by_type[t] and len(chosen) < LABEL_COUNT:
                chosen.append(by_type[t].pop())
    chosen.sort(key=lambda r: (r.type or "", r.language or "", r.record_id))
    sheet = settings.data_dir / SHEET_PATH
    labels = settings.data_dir / LABELS_PATH
    lines = ["# 사람 라벨 시트", "",
             "Judge와 같은 루브릭(research/gold_metric_selection.md의 \"항목 상세\")으로 판정해 "
             f"`data/{LABELS_PATH}`의 빈칸(null)을 채운다. 인용과 요점은 true/false, 품질 항목은 \"pass\", \"fail\", \"na\"다.", ""]
    async with open_query_service(settings) as parts:
        for n, r in enumerate(chosen, start=1):
            item = items[r.item_id or ""]
            context = [h.chunk for h in (await parts.retriever.retrieve(r.question, load_config(Path("configs/baseline.toml")).top_k)).hits]
            lines += [f"## {n}. `{r.record_id.split(':')[1]}` ({r.type}, {r.language})", "", f"**질문**: {r.question}", "",
                      "**답**:", "", "```text", r.answer, "```", "", "**인용 판정 대상**(문장, 가리키는 근거 번호):", ""]
            lines += [f"{i}. [{ref}] {sentence}" for i, (sentence, ref) in enumerate(citation_pairs(r.answer))]
            lines += ["", "**핵심 요점**:", ""] + [f"{i}. {p}" for i, p in enumerate(item.acceptance_criteria or [])]
            lines += ["", "**금지 내용**:", ""] + [f"{i}. {p}" for i, p in enumerate(item.rejection_criteria or [])] + [""]
            lines += ["<details><summary>근거 문서</summary>", ""]
            for k, chunk in enumerate(context, start=1):
                lines += [f"**[{k}] {chunk.doc_id}**", "", "```text", chunk.text, "```", ""]
            lines += ["</details>", ""]
    sheet.write_text("\n".join(lines), encoding="utf-8")
    if not labels.exists():
        rows = [HumanLabel(
            record_id=r.record_id, item_id=r.item_id or "", language=r.language or "", type=r.type or "",
            citations=[None] * len(citation_pairs(r.answer)), key_points=[None] * len(items[r.item_id or ""].acceptance_criteria or []),
            rejections=[None] * len(items[r.item_id or ""].rejection_criteria or []),
        ) for r in chosen]
        labels.write_text("".join(row.model_dump_json() + "\n" for row in rows), encoding="utf-8")
    return sheet, labels


async def agreement(settings: Settings) -> tuple[list[AgreementRow], int, int]:
    """사람 라벨을 다 채운 기록만 Judge 3회 다수결과 비교한다. (항목별 결과, 채운 기록 수, 전체 라벨 수)."""
    labels = [HumanLabel.model_validate_json(line)
              for line in (settings.data_dir / LABELS_PATH).read_text(encoding="utf-8").splitlines() if line.strip()]
    _, grouped, _ = await load_run(settings, "configs/baseline.toml", None)
    rows = compare(labels, grouped)
    return rows, sum(label.complete() for label in labels), len(labels)


def main(argv: list[str] | None = None) -> int:
    """validity는 기대한 하락이 하나라도 없으면 종료 코드 1이다."""
    parser = argparse.ArgumentParser(prog="judge-check")
    parser.add_argument("command", choices=["validity", "label-sheet", "agreement"])
    args = parser.parse_args(argv)
    settings = get_settings()
    if args.command == "validity":
        checks = asyncio.run(validity(settings))
        _write(settings.research_dir / VALIDITY_OUT / "results.json", [c.model_dump(mode="json") for c in checks])
        for c in checks:
            logger.info("validity_checked", variant=c.variant, passed=c.passed)
        return 0 if all(c.passed for c in checks) else 1
    if args.command == "label-sheet":
        sheet, labels = asyncio.run(label_sheet(settings))
        logger.info("label_sheet_written", sheet=str(sheet), labels=str(labels))
        return 0
    rows, complete, total = asyncio.run(agreement(settings))
    _write(settings.research_dir / AGREEMENT_OUT / "results.json",
           {"labeled_records": complete, "total_records": total, "items": [r.model_dump(mode="json") for r in rows]})
    for r in rows:
        logger.info("agreement_checked", item=r.item, pairs=r.pairs, agreement=r.agreement, kappa=r.kappa)
    return 0


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
