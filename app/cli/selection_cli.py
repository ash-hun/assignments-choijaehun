"""선정 실험 실행 명령. 지금은 데이터셋 선정의 closed-book 검증을 제공한다."""
import sys
import json
import asyncio
import argparse
from pathlib import Path
from openai import AsyncOpenAI

from app.schema.selection_schema import ClosedBookAnswer, ClosedBookQuestion
from app.service.eval.closed_book_prober import ClosedBookProber
from app.service.eval.closed_book_reporter import summarize
from app.common.settings import Settings, get_settings
from app.client.llm_client import LlmClient
from app.common.logger import get_logger

QUESTIONS_DIR = "selection/closed_book"
ANSWERS_DIR = "artifacts/closed_book"
GRADING_KEY = "grading_key.jsonl"
GRADES = "grades.jsonl"
SUMMARY = "summary.json"

logger = get_logger(__name__)


def build_llm(settings: Settings) -> LlmClient:
    """설정에서 LLM 클라이언트를 조립한다. 키나 엔드포인트가 없으면 바로 실패한다."""
    if not (settings.elice_serverless_api_key and settings.llm_base_url and settings.llm_model):
        raise SystemExit("ELICE_SERVERLESS_API_KEY, LLM_BASE_URL, LLM_MODEL must be set")
    sdk = AsyncOpenAI(
        api_key=settings.elice_serverless_api_key.get_secret_value(),
        base_url=settings.llm_base_url,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
    )
    return LlmClient(sdk, settings.llm_model)


def load_questions(path: Path) -> list[ClosedBookQuestion]:
    """JSONL 문항 파일을 읽는다."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return [ClosedBookQuestion.model_validate_json(line) for line in lines if line.strip()]


async def run_closed_book(settings: Settings, names: list[str] | None, repeats: int) -> None:
    """후보마다 답변을 받아 모델별 파일로 저장한다. 같은 모델로 다시 돌리면 같은 파일을 덮어쓴다."""
    llm = build_llm(settings)
    seeds = [settings.llm_seed + i for i in range(repeats)]
    prober = ClosedBookProber(llm, seeds, settings.llm_concurrency, settings.llm_temperature)
    files = sorted((settings.data_dir / QUESTIONS_DIR).glob("*.jsonl"))
    out_dir = settings.research_dir / ANSWERS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    for path in files:
        corpus = path.stem
        if names and corpus not in names:
            continue
        answers = await prober.probe(corpus, load_questions(path))
        safe_model = llm.model.replace("/", "_")
        out = out_dir / f"{corpus}__{safe_model}.jsonl"
        out.write_text("".join(a.model_dump_json() + "\n" for a in answers), encoding="utf-8")
        logger.info("closed_book_written", path=str(out), answers=len(answers))


def report_closed_book(settings: Settings) -> None:
    """블라인드 채점 결과를 답변에 붙이고 후보별 요약을 저장한다. 입력이 같으면 출력도 같다."""
    out_dir = settings.research_dir / ANSWERS_DIR
    key = [json.loads(line) for line in (out_dir / GRADING_KEY).read_text(encoding="utf-8").splitlines() if line]
    grades = [json.loads(line) for line in (out_dir / GRADES).read_text(encoding="utf-8").splitlines() if line]
    grade_by_blind = {g["blind_id"]: g["grade"] for g in grades}
    if set(grade_by_blind) != {k["blind_id"] for k in key}:
        raise SystemExit("grades do not cover the grading key exactly")
    grade_by_answer = {(k["id"], k["seed"]): grade_by_blind[k["blind_id"]] for k in key}

    answers: list[ClosedBookAnswer] = []
    for path in sorted(out_dir.glob("*__*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            answer = ClosedBookAnswer.model_validate_json(line)
            answers.append(answer.model_copy(update={"grade": grade_by_answer[(answer.id, answer.seed)]}))
    summaries = [s.model_dump() for s in summarize(answers)]
    (out_dir / SUMMARY).write_text(json.dumps(summaries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    logger.info("closed_book_summary_written", corpora=len(summaries))


def main(argv: list[str] | None = None) -> int:
    """closed-book: 문서 없이 후보별 문항에 답을 받는다. closed-book-report: 채점 결과를 집계한다."""
    parser = argparse.ArgumentParser(prog="select")
    parser.add_argument("experiment", choices=["closed-book", "closed-book-report"])
    parser.add_argument("--name", action="append", help="대상 후보 이름. 생략하면 전부")
    parser.add_argument("--repeats", type=int, default=3, help="문항당 질의 횟수. seed를 하나씩 늘려 반복한다")
    args = parser.parse_args(argv)
    if args.experiment == "closed-book-report":
        report_closed_book(get_settings())
        return 0
    asyncio.run(run_closed_book(get_settings(), args.name, args.repeats))
    return 0


if __name__ == "__main__":
    sys.exit(main())
