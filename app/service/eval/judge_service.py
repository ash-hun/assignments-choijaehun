"""기록마다 Judge를 불러 판정을 저장한다. 같은 요청은 캐시가, 같은 판정 키는 저장소가 받아 다시 돌려도 비용이 들지 않는다."""
import json
import asyncio

from app.service.eval.judge_prompt import PROMPT_VERSION, RUBRIC_SCHEMA, CITATION_SCHEMA, prompt_hash, rubric_messages, citation_messages
from app.service.eval.judge_metric import parse_rubric, citation_pairs, parse_citations
from app.client.llm_client import ChatMessage, LlmClient, LlmCompletion
from app.repository.eval_record_repository import EvalRecordRepository
from app.service.query.chunk_retriever import ChunkRetriever
from app.schema.judge_schema import JudgeKind, JudgeResult
from app.common.upstream_error import UpstreamError
from app.schema.eval_schema import EvalRecord
from app.schema.gold_schema import GoldItem
from app.client.llm_cache import LlmCache
from app.schema.chunk_schema import Chunk
from app.common.logger import get_logger

# 추론 토큰을 쓰는 모델이다. 전체 판정에서 루브릭 출력 16건이 비스트리밍 상한(2,000)에 걸려 JSON이 끊겨,
# 상한이 없는 스트리밍으로 부르고 넉넉히 둔다. 상한까지 쓴 판정은 1,986토큰이었다.
MAX_COMPLETION_TOKENS = 6000
# 파일럿에서 인용 19개를 한 번에 보낸 호출이 출력 상한에 걸려 JSON이 끊겼다. 묶음을 나눠 부른다.
CITATION_BATCH = 8

logger = get_logger(__name__)


class JudgeService:
    """답한 기록만 판정한다. 근거 청크는 같은 검색기로 다시 찾는다(질의 경로의 검색은 같은 입력이면 같은 결과다)."""

    def __init__(
        self, llm: LlmClient, cache: LlmCache, repository: EvalRecordRepository, retriever: ChunkRetriever,
        chunks: list[Chunk], concurrency: int,
    ) -> None:
        self._llm = llm
        self._cache = cache
        self._repository = repository
        self._retriever = retriever
        self._chunks = {c.chunk_id: c for c in chunks}
        self._semaphore = asyncio.Semaphore(concurrency)
        # 문구를 고치면 해시가 바뀌어 이전 판정을 다시 쓰지 않는다.
        self.version = f"{PROMPT_VERSION}-{prompt_hash()}"

    async def current(self, run_id: str) -> list[JudgeResult]:
        """이 Judge 모델과 프롬프트 버전의 판정만."""
        return [r for r in await self._repository.judgments(run_id)
                if r.judge_model == self._llm.model and r.prompt_version == self.version]

    async def judge(
        self, run_id: str, records: list[EvalRecord], items: dict[str, GoldItem], samples: int, top_k: int,
    ) -> list[JudgeResult]:
        """성공한 판정이 없는 (기록, 종류, 표본)만 부른다. 호출 자체가 실패하면 저장하지 않는다."""
        # 실패한 판정은 다시 부른다. 같은 요청이면 캐시가 같은 응답을 돌려줘 비용이 들지 않는다.
        done = {(r.record_id, r.kind, r.sample) for r in await self.current(run_id) if r.ok}
        jobs = []
        for record in records:
            if record.status != "answered":
                continue
            context = [h.chunk for h in await self._retriever.retrieve(record.question, top_k)]
            item = items.get(record.item_id or "")
            for sample in range(samples):
                for kind in ("citation", "rubric"):
                    if (record.record_id, kind, sample) not in done:
                        jobs.append(self._one(record, item, context, kind, sample))
        fresh = [r for r in await asyncio.gather(*jobs) if r is not None]
        logger.info("judge_done", run_id=run_id, new=len(fresh), skipped=len(done), failed_calls=len(jobs) - len(fresh))
        return await self.current(run_id)

    async def _one(
        self, record: EvalRecord, item: GoldItem | None, context: list[Chunk], kind: JudgeKind, sample: int,
    ) -> JudgeResult | None:
        claims = citation_pairs(record.answer)
        key_points = (item.acceptance_criteria or []) if item else []
        rejections = (item.rejection_criteria or []) if item else []
        batches = [claims[i:i + CITATION_BATCH] for i in range(0, len(claims), CITATION_BATCH)]
        calls = [citation_messages(context, batch) for batch in batches] if kind == "citation" else [
            rubric_messages(context, record.question, record.answer, key_points, rejections)]
        try:
            completions = [await self._call(messages, kind, sample) for messages in calls]
        except UpstreamError as e:
            logger.warning("judge_call_failed", record=record.record_id, kind=kind, sample=sample, cause=type(e.__cause__).__name__)
            return None
        raws = [_json(c.text) for c in completions]
        citations: list[bool] | None = None
        rubric = None
        if kind == "citation":
            parsed = [parse_citations(raw, len(batch)) if raw is not None else None for raw, batch in zip(raws, batches)]
            citations = None if any(p is None for p in parsed) else [v for p in parsed if p is not None for v in p]
        elif raws[0] is not None:
            rubric = parse_rubric(raws[0], len(key_points), len(rejections))
        result = JudgeResult(
            record_id=record.record_id, kind=kind, sample=sample, judge_model=self._llm.model, prompt_version=self.version,
            ok=citations is not None or rubric is not None, citations=citations, rubric=rubric,
            input_tokens=sum(c.input_tokens for c in completions), output_tokens=sum(c.output_tokens for c in completions),
        )
        if not result.ok:
            logger.warning("judge_output_rejected", record=record.record_id, kind=kind, sample=sample)
        await self._repository.upsert_judgment(result)
        return result

    async def _call(self, messages: list[ChatMessage], kind: JudgeKind, sample: int) -> LlmCompletion:
        # 표본마다 다른 키를 써야 temperature 0에서도 표본이 캐시 하나로 합쳐지지 않는다. seed는 게이트웨이가 거부해 키에만 쓴다.
        schema = CITATION_SCHEMA if kind == "citation" else RUBRIC_SCHEMA
        key = LlmCache.key(self._llm.model, messages, sample, 0.0, MAX_COMPLETION_TOKENS)
        cached = self._cache.get(key)
        if cached is not None:
            return cached[0]
        completion: LlmCompletion | None = None
        async with self._semaphore:
            async for event in self._llm.stream(messages, seed=None, max_completion_tokens=MAX_COMPLETION_TOKENS,
                                                temperature=0.0, json_schema=schema):
                if isinstance(event, LlmCompletion):
                    completion = event
        if completion is None:
            raise UpstreamError("judge stream ended without a completion")
        self._cache.put(key, completion, 0.0)
        return completion


def _json(text: str) -> dict[str, object] | None:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None
