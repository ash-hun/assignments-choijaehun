"""LLM 선정 실험 진입점. 확정 검색 구성으로 dev set 근거를 한 번 찾고, 후보마다 답을 받아 재고 판정을 저장한다."""
import sys
import json
import asyncio
import argparse
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient

from app.service.eval.llm_benchmark import LlmRun, LlmAnswer, LlmBenchmark, LlmCandidate, RetrievedItem, pick_llm, summarize_llm
from app.cli.embedding_crosscheck_cli import CHUNK_METHOD, CHUNK_SIZE, CHUNK_OVERLAP, INCUMBENT, make_client
from app.repository.qdrant_chunk_repository import QdrantChunkRepository
from app.service.eval.embedding_benchmark import EmbeddingBenchmark
from app.service.query.evidence_checker import EvidenceChecker
from app.service.ingest.chunk_splitter import ChunkSplitter
from app.cli.chunking_selection_cli import load_corpus
from app.common.settings import Settings, get_settings
from app.cli.embedding_selection_cli import load_gold
from app.schema.vector_schema import IndexContract
from app.client.llm_client import LlmClient
from app.client.llm_cache import LlmCache
from app.common.logger import get_logger

OUTPUT_DIR = "artifacts/llm_selection"
COLLECTION = "llm_selection"
# 생성 단계에 넣는 근거 수. 6단계의 근거 보존@5와 같은 기준이다.
CONTEXT_K = 5
# research/refusal_threshold.md에서 확정.
REFUSAL_THRESHOLD = 0.6375
# 엔드포인트는 LLM_CANDIDATE_URLS 환경변수로 받는다. 두 모델 모두 seed를 거부하고(400) temperature 0을 받는다.
# 단가는 엘리스 ML API 모델 라이브러리의 Serverless 요금(VAT 별도, 캐시 할인 미반영)이다.
CANDIDATES = [
    LlmCandidate(name="claude-haiku-5-5", input_krw_per_mtok=141.0, output_krw_per_mtok=708.0, temperature=0.0, seeds=[None]),
    LlmCandidate(name="gemini-3.8-flash", input_krw_per_mtok=1063.0, output_krw_per_mtok=5315.0, temperature=0.0, seeds=[None]),
]

logger = get_logger(__name__)


async def retrieve(settings: Settings) -> list[RetrievedItem]:
    """확정 구성(Qwen3, structure-512-77, dense 정확 검색)으로 dev set 전 문항의 상위 근거와 최고 점수를 찾는다."""
    documents = load_corpus(settings)
    gold = load_gold(settings)
    repository = QdrantChunkRepository(AsyncQdrantClient(url=settings.qdrant_url, prefer_grpc=True, timeout=60))
    client, _ = make_client(settings, INCUMBENT)
    splitter = ChunkSplitter(CHUNK_METHOD, CHUNK_SIZE, CHUNK_OVERLAP, client.token_count, client.token_offsets)
    chunks = [c for d in documents for c in splitter.split(d)]
    by_id = {c.chunk_id: c for c in chunks}
    contract = IndexContract(embedding_model=client.model_name, tokenizer="model-native", chunk_config_hash=splitter.name)
    await EmbeddingBenchmark(repository).index(client, COLLECTION, contract, chunks)
    items = []
    for language, group in gold.items():
        for item, vector in zip(group, client.embed_queries([i.question for i in group])):
            hits = await repository.search_dense_scored(COLLECTION, vector, CONTEXT_K, exact=True)
            items.append(RetrievedItem(
                item_id=str(item.id), language=language, type=item.type, answerable=item.answerable, question=item.question,
                top_score=hits[0][1], chunks=[by_id[chunk_id] for chunk_id, _ in hits],
            ))
    await repository.drop_collection(COLLECTION)
    return items


async def run(settings: Settings, names: list[str] | None) -> tuple[list[LlmAnswer], list[LlmRun]]:
    """후보를 하나씩 돈다. 응답은 캐시에 쌓여 다시 돌리면 API를 부르지 않는다."""
    key = settings.elice_serverless_api_key
    if key is None:
        raise SystemExit("ELICE_SERVERLESS_API_KEY must be set")
    candidates = [c for c in CANDIDATES if not names or c.name in names]
    missing = [c.name for c in candidates if c.name not in settings.llm_candidate_urls]
    if missing:
        raise SystemExit(f"LLM_CANDIDATE_URLS has no endpoint for: {', '.join(missing)}")
    items = await retrieve(settings)
    out = settings.research_dir / OUTPUT_DIR
    benchmark = LlmBenchmark(EvidenceChecker(REFUSAL_THRESHOLD), LlmCache(out / "responses.jsonl"), settings.llm_concurrency)
    answers: list[LlmAnswer] = []
    runs: list[LlmRun] = []
    for candidate in candidates:
        sdk = AsyncOpenAI(api_key=key.get_secret_value(), base_url=settings.llm_candidate_urls[candidate.name],
                          timeout=settings.llm_timeout_seconds, max_retries=settings.llm_max_retries)
        result = await benchmark.run(LlmClient(sdk, candidate.name), candidate, items)
        answers += result
        runs += summarize_llm(candidate, result)
        await sdk.close()
    return answers, runs


def write(settings: Settings, answers: list[LlmAnswer], runs: list[LlmRun]) -> None:
    """문항별 답, 요약, 판정을 쓴다. 캐시가 그대로면 같은 파일이 나온다."""
    out = settings.research_dir / OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)
    (out / "answers.jsonl").write_text("".join(a.model_dump_json() + "\n" for a in answers), encoding="utf-8")
    (out / "results.json").write_text(json.dumps([r.model_dump() for r in runs], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    verdict = pick_llm(runs)
    (out / "verdict.json").write_text(json.dumps(verdict.model_dump(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    logger.info("llm_results_written", path=str(out), passed=verdict.passed, chosen=verdict.chosen)


def main(argv: list[str] | None = None) -> int:
    """--model로 일부 후보만 돌릴 수 있다. 결과 파일은 돌린 후보만으로 덮어쓴다."""
    parser = argparse.ArgumentParser(prog="llm-selection")
    parser.add_argument("--model", action="append", help="후보 모델 이름. 생략하면 전부")
    args = parser.parse_args(argv)
    settings = get_settings()
    answers, runs = asyncio.run(run(settings, args.model))
    write(settings, answers, runs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
