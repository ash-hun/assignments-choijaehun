"""Gold Set 평가 진입점(`make eval`). 설정 파일 하나로 test set 전체를 실제 질의 경로에 넣고 기록 저장소와 Report를 남긴다."""
import sys
import asyncio
import hashlib
import tomllib
import argparse
from pathlib import Path
from openai import AsyncOpenAI
from dataclasses import dataclass
from psycopg import AsyncConnection
from collections.abc import Callable

from app.service.eval.validity_variant import NeverRefuseChecker, RandomChunkRetriever, strip_citations, shuffle_citations
from app.service.eval.pipeline_identity import answer_prompt_hash, pipeline_config_id
from app.service.eval.eval_service import TokenPrice, EvalOutcome, EvalService
from app.service.query.query_builder import QueryParts, open_query_service
from app.repository.eval_record_repository import EvalRecordRepository
from app.schema.judge_schema import JudgeResult, RecordJudgment
from app.service.eval.eval_summarizer import summarize_records
from app.service.query.evidence_checker import EvidenceChecker
from app.service.query.chunk_retriever import ChunkRetriever
from app.service.eval.retrieval_metric import BOOTSTRAP_SEED
from app.schema.eval_schema import EvalConfig, EvalManifest
from app.service.query.query_service import QueryService
from app.service.eval.report_writer import write_report
from app.service.eval.judge_service import JudgeService
from app.common.settings import Settings, get_settings
from app.service.eval.judge_metric import aggregate
from app.client.llm_client import LlmClient
from app.schema.gold_schema import GoldItem
from app.client.llm_cache import LlmCache
from app.schema.chunk_schema import Chunk
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
    corpus_manifest = settings.data_dir / "corpus" / "manifests" / f"{settings.corpus_name}.json"
    return EvalManifest(
        config=config, config_id=pipeline_config_id(settings, config.top_k), gold_hashes=gold_hashes,
        corpus_manifest_hash=_sha256(corpus_manifest.read_bytes()), index_contract=contract.model_dump(),
        collection=contract.collection_name(settings.corpus_name), answer_model=settings.answer_llm_model,
        answer_temperature=settings.answer_temperature, answer_seed=settings.answer_seed,
        answer_max_tokens=settings.answer_max_tokens, refusal_threshold=settings.refusal_threshold,
        prompt_hash=answer_prompt_hash(), bootstrap_seed=BOOTSTRAP_SEED, git_commit=settings.git_commit,
    )


@dataclass(frozen=True)
class RunResult:
    """평가 한 번의 결과. Judge를 부르지 않았으면 judgments와 judge_info가 None이다."""

    run_id: str
    manifest: EvalManifest
    outcome: EvalOutcome
    judgments: dict[str, RecordJudgment] | None
    judge_info: dict[str, str] | None


def variant_parts(
    config: EvalConfig, settings: Settings, parts: QueryParts, chunks: list[Chunk],
) -> tuple[QueryService, ChunkRetriever, Callable[[str], str] | None]:
    """설정의 변형대로 질의 서비스, 검색기, 답 변환을 고른다. none이면 서비스 그대로다.

    swapped_context는 서비스와 검색 지표는 그대로이고, Judge가 근거로 받는 청크만 바꾼다(judge_retriever).
    """
    if config.variant in ("none", "swapped_context"):
        return parts.service, parts.retriever, None
    if config.variant == "shuffled_citations":
        return parts.service, parts.retriever, lambda answer: shuffle_citations(answer, config.top_k)
    if config.variant == "stripped_citations":
        return parts.service, parts.retriever, strip_citations
    retriever = RandomChunkRetriever(chunks, BOOTSTRAP_SEED) if config.variant == "random_chunks" else parts.retriever
    checker = NeverRefuseChecker() if config.variant == "no_refusal" else EvidenceChecker(settings.refusal_threshold)
    service = QueryService(retriever, checker, parts.llm, parts.gate, settings.embedding_model, settings.default_top_k,
                           settings.answer_temperature, settings.answer_seed, settings.answer_max_tokens)
    return service, retriever, None


async def run(settings: Settings, config: EvalConfig, judge_limit: int | None) -> RunResult:
    """저장소 스키마를 맞추고, 실행을 기록하고, 기록이 없는 문항만 돌고, 판정이 없는 답만 Judge에 보낸다."""
    if settings.eval_db_password is None:
        raise SystemExit("EVAL_DB_PASSWORD must be set")
    judge_url = settings.judge_llm_base_url or settings.llm_candidate_urls.get(settings.judge_llm_model)
    if config.judge_samples and (judge_url is None or settings.elice_serverless_api_key is None):
        raise SystemExit(f"JUDGE_LLM_BASE_URL (or LLM_CANDIDATE_URLS[{settings.judge_llm_model}]) must be set")
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
        service, retriever, transform = variant_parts(config, settings, parts, chunks)
        price = TokenPrice(input_krw_per_mtok=settings.answer_input_krw_per_mtok,
                           output_krw_per_mtok=settings.answer_output_krw_per_mtok)
        outcome = await EvalService(service, retriever, repository, price, transform).run(
            run_id, manifest.config_id, config, items, chunks,
        )
        if not config.judge_samples or judge_url is None or settings.elice_serverless_api_key is None:
            return RunResult(run_id=run_id, manifest=manifest, outcome=outcome, judgments=None, judge_info=None)
        sdk = AsyncOpenAI(api_key=settings.elice_serverless_api_key.get_secret_value(), base_url=judge_url,
                          timeout=settings.llm_timeout_seconds, max_retries=settings.llm_max_retries)
        judge_retriever = RandomChunkRetriever(chunks, BOOTSTRAP_SEED) if config.variant == "swapped_context" else retriever
        judge = JudgeService(LlmClient(sdk, settings.judge_llm_model), LlmCache(settings.judge_cache_path), repository,
                             judge_retriever, settings.llm_concurrency)
        answered = [r for r in outcome.records if r.status == "answered"]
        targets = answered[:judge_limit] if judge_limit is not None else answered
        by_id = {str(i.id): i for i in items}
        results = await judge.judge(targets, by_id, config.judge_samples, config.top_k)
        await sdk.close()
    grouped: dict[str, list[JudgeResult]] = {}
    for result in results:
        if result.sample < config.judge_samples:
            grouped.setdefault(result.record_id, []).append(result)
    judgments = {
        r.record_id: aggregate(r, grouped.get(r.record_id, []), bool(by_id.get(r.item_id or "") and by_id[r.item_id or ""].acceptance_criteria))
        for r in targets
    }
    tokens_in = sum(r.input_tokens for r in results)
    tokens_out = sum(r.output_tokens for r in results)
    cost = tokens_in * settings.judge_input_krw_per_mtok / 1e6 + tokens_out * settings.judge_output_krw_per_mtok / 1e6
    version = ", ".join(f"{kind} {v}" for kind, v in judge.versions.items())
    judge_info = {"model": settings.judge_llm_model, "version": version, "samples": str(config.judge_samples),
                  "calls": str(len(results)), "cost_krw": f"{cost:.1f}"}
    return RunResult(run_id=run_id, manifest=manifest, outcome=outcome, judgments=judgments, judge_info=judge_info)


def main(argv: list[str] | None = None) -> int:
    """평가를 돌리고 Report를 쓴다. 실패한 문항이 있으면 Report는 쓰되 종료 코드 1이고, 다시 돌리면 그 문항만 부른다."""
    parser = argparse.ArgumentParser(prog="eval-run")
    parser.add_argument("--config", type=Path, required=True, help="configs/*.toml")
    parser.add_argument("--judge-limit", type=int, default=None, help="파일럿용. 답한 기록 중 앞의 N개만 Judge에 보낸다")
    args = parser.parse_args(argv)
    settings = get_settings()
    config = load_config(args.config)
    result = asyncio.run(run(settings, config, args.judge_limit))
    records = result.outcome.records
    summaries = summarize_records(records, settings.refusal_threshold, result.judgments)
    write_report(settings.reports_dir, result.run_id, result.manifest, records, summaries, result.outcome.failed,
                 result.judgments, result.judge_info)
    logger.info("eval_report_written", path=str(settings.reports_dir / result.run_id), failed=len(result.outcome.failed),
                judge=result.judge_info)
    return 1 if result.outcome.failed else 0


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


if __name__ == "__main__":
    sys.exit(main())
