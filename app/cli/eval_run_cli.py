"""Gold Set 평가 진입점(`make eval`). 설정 파일 하나로 test set 전체를 실제 질의 경로에 넣고 기록 저장소와 Report를 남긴다."""
import sys
import json
import asyncio
import hashlib
import tomllib
import argparse
from pathlib import Path
from psycopg import AsyncConnection

from app.service.eval.eval_service import TokenPrice, EvalOutcome, EvalService
from app.repository.eval_record_repository import EvalRecordRepository
from app.service.eval.eval_summarizer import summarize_records
from app.service.query.query_builder import open_query_service
from app.service.eval.retrieval_metric import BOOTSTRAP_SEED
from app.service.query.prompt_builder import build_messages
from app.schema.eval_schema import EvalConfig, EvalManifest
from app.service.eval.report_writer import write_report
from app.common.settings import Settings, get_settings
from app.schema.gold_schema import GoldItem
from app.common.logger import get_logger
from app.cli.eval_cli import read_gold

logger = get_logger(__name__)


def load_config(path: Path) -> EvalConfig:
    """TOML 설정을 읽고 검증한다."""
    return EvalConfig.model_validate(tomllib.loads(path.read_text(encoding="utf-8")))


def load_items(config: EvalConfig) -> tuple[list[GoldItem], dict[str, str]]:
    """설정의 Gold 파일을 순서대로 읽는다. 스키마 문제가 하나라도 있으면 멈춘다. 파일별 sha256도 돌려준다."""
    items: list[GoldItem] = []
    hashes: dict[str, str] = {}
    for name in config.gold_files:
        path = Path(name)
        loaded, problems = read_gold(path)
        if problems:
            raise SystemExit(f"{name} has problems: {problems[:3]}")
        items += loaded
        hashes[name] = _sha256(path.read_bytes())
    return items, hashes


def build_manifest(settings: Settings, config: EvalConfig, gold_hashes: dict[str, str]) -> EvalManifest:
    """재현에 필요한 값을 모은다. config_id는 파이프라인 구성만의 해시라 Gold Set 평가와 실시간 질의가 같은 값을 쓴다."""
    contract = settings.index_contract()
    prompt = json.dumps([m.model_dump() for m in build_messages("{question}", [])], ensure_ascii=False)
    prompt_hash = _sha256(prompt.encode())[:12]
    pipeline = {
        "index_contract": contract.model_dump(), "answer_model": settings.answer_llm_model, "prompt_hash": prompt_hash,
        "refusal_threshold": settings.refusal_threshold, "top_k": config.top_k,
    }
    corpus_manifest = settings.data_dir / "corpus" / "manifests" / f"{settings.corpus_name}.json"
    return EvalManifest(
        config=config, config_id=_sha256(json.dumps(pipeline, sort_keys=True).encode())[:12], gold_hashes=gold_hashes,
        corpus_manifest_hash=_sha256(corpus_manifest.read_bytes()), index_contract=contract.model_dump(),
        collection=contract.collection_name(settings.corpus_name), answer_model=settings.answer_llm_model,
        answer_temperature=settings.answer_temperature, answer_seed=settings.answer_seed,
        answer_max_tokens=settings.answer_max_tokens, refusal_threshold=settings.refusal_threshold,
        prompt_hash=prompt_hash, bootstrap_seed=BOOTSTRAP_SEED, git_commit=settings.git_commit,
    )


async def run(settings: Settings, config: EvalConfig) -> tuple[str, EvalManifest, EvalOutcome]:
    """저장소 스키마를 맞추고, 실행을 기록하고, 기록이 없는 문항만 돈다."""
    if settings.eval_db_password is None:
        raise SystemExit("EVAL_DB_PASSWORD must be set")
    items, gold_hashes = load_items(config)
    manifest = build_manifest(settings, config, gold_hashes)
    run_id = manifest.run_id()
    conn = await AsyncConnection.connect(
        host=settings.eval_db_host, port=settings.eval_db_port, dbname=settings.eval_db_name, user=settings.eval_db_user,
        password=settings.eval_db_password.get_secret_value(), autocommit=True, connect_timeout=10,
    )
    async with conn, open_query_service(settings) as parts:
        repository = EvalRecordRepository(conn)
        await repository.ensure_schema()
        await repository.upsert_run(run_id, manifest)
        chunks = await parts.repository.all_chunks(parts.collection)
        price = TokenPrice(input_krw_per_mtok=settings.answer_input_krw_per_mtok,
                           output_krw_per_mtok=settings.answer_output_krw_per_mtok)
        outcome = await EvalService(parts.service, parts.retriever, repository, price).run(
            run_id, manifest.config_id, config, items, chunks,
        )
    return run_id, manifest, outcome


def main(argv: list[str] | None = None) -> int:
    """평가를 돌리고 Report를 쓴다. 실패한 문항이 있으면 Report는 쓰되 종료 코드 1이고, 다시 돌리면 그 문항만 부른다."""
    parser = argparse.ArgumentParser(prog="eval-run")
    parser.add_argument("--config", type=Path, required=True, help="configs/*.toml")
    args = parser.parse_args(argv)
    settings = get_settings()
    config = load_config(args.config)
    run_id, manifest, outcome = asyncio.run(run(settings, config))
    summaries = summarize_records(outcome.records, settings.refusal_threshold)
    write_report(settings.reports_dir, run_id, manifest, outcome.records, summaries, outcome.failed)
    logger.info("eval_report_written", path=str(settings.reports_dir / run_id), failed=len(outcome.failed))
    return 1 if outcome.failed else 0


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


if __name__ == "__main__":
    sys.exit(main())
