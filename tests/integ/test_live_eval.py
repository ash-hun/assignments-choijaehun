"""live_eval 기능의 HTTP 통합 테스트. 실제 앱에 메모리 저장소, 임베딩, 대체 답변 LLM과 Judge를 넣어 기록, 채점, 집계를 확인한다."""
import json
import time
import asyncio
from typing import Any
from pathlib import Path
from fastapi.testclient import TestClient
from collections.abc import Iterator, AsyncIterator
from contextlib import contextmanager, asynccontextmanager

from tests.integ.memory_backend import MemoryChunkRepository, MemoryEmbeddingClient, MemoryEvalRecordRepository
from app.client.llm_client import LlmDelta, ChatMessage, LlmClient, LlmCompletion
from app.service.live.live_judge_worker import JudgeBudget, LiveJudgeWorker
from app.service.live.live_metric_service import LiveMetricService
from app.service.query.evidence_checker import EvidenceChecker
from app.service.query.chunk_retriever import ChunkRetriever
from app.service.query.query_service import QueryService
from app.service.eval.judge_service import JudgeService
from app.service.live.live_recorder import LiveRecorder
from app.service.eval.eval_service import TokenPrice
from app.service.live.live_builder import LiveEval
from app.service.live.live_signal import LiveSignal
from app.service.query.llm_gate import LlmGate
from app.api.query_runtime import QueryRuntime
from app.client.llm_cache import LlmCache
from app.schema.chunk_schema import Chunk
from app.common.settings import Settings
from app.main import create_app

CACHE = "The cache directory defaults to the user cache folder and can be moved with UV_CACHE_DIR."
PRICE = TokenPrice(input_krw_per_mtok=100.0, output_krw_per_mtok=1000.0)


class AnswerLlm(LlmClient):
    def __init__(self) -> None:
        pass

    @property
    def model(self) -> str:
        return "answer"

    async def complete(self, messages: list[ChatMessage], seed: int | None, max_completion_tokens: int,
                       temperature: float | None = None, json_schema: dict[str, Any] | None = None) -> LlmCompletion:
        return LlmCompletion(text="Set UV_CACHE_DIR [1].", model="answer", input_tokens=40, output_tokens=6)

    async def stream(self, messages: list[ChatMessage], seed: int | None, max_completion_tokens: int,
                     temperature: float | None = None, json_schema: dict[str, Any] | None = None) -> AsyncIterator[LlmDelta | LlmCompletion]:
        yield LlmDelta(text="Set UV_CACHE_DIR [1].")
        yield LlmCompletion(text="Set UV_CACHE_DIR [1].", model="answer", input_tokens=40, output_tokens=6)


class JudgeLlm(LlmClient):
    def __init__(self) -> None:
        self.calls = 0

    @property
    def model(self) -> str:
        return "judge"

    async def complete(self, messages: list[ChatMessage], seed: int | None, max_completion_tokens: int,
                       temperature: float | None = None, json_schema: dict[str, Any] | None = None) -> LlmCompletion:
        raise AssertionError("judge uses the streaming path")

    async def stream(self, messages: list[ChatMessage], seed: int | None, max_completion_tokens: int,
                     temperature: float | None = None, json_schema: dict[str, Any] | None = None) -> AsyncIterator[LlmDelta | LlmCompletion]:
        self.calls += 1
        if "<claims>" in messages[-1].content:
            body: dict[str, Any] = {"judgments": [{"id": 0, "supported": True}]}
        else:
            body = {"key_points": [], "rejections": [], "unsupported_claim": "pass", "identifier_accuracy": "pass",
                    "interface_separation": "na", "version_status": "na", "prior_knowledge": "pass", "reason": ""}
        yield LlmCompletion(text=json.dumps(body), model="judge", input_tokens=1000, output_tokens=100)


@contextmanager
def serve(tmp_path: Path, live_enabled: bool = True) -> Iterator[tuple[TestClient, MemoryEvalRecordRepository, JudgeLlm]]:
    settings = Settings(_env_file=None)
    contract = settings.index_contract()
    collection = contract.collection_name(settings.corpus_name)
    chunks_repo, embedding = MemoryChunkRepository(), MemoryEmbeddingClient()
    chunks = [Chunk(chunk_id=Chunk.make_id("cache.md", CACHE), doc_id="cache.md", ordinal=0, text=CACHE, title="cache.md")]

    async def index() -> None:
        await chunks_repo.ensure_collection(collection, 256, contract)
        await chunks_repo.upsert(collection, chunks, embedding.embed_documents([CACHE]), [])

    asyncio.run(index())
    records, judge_llm = MemoryEvalRecordRepository(), JudgeLlm()

    @asynccontextmanager
    async def builder(s: Settings) -> AsyncIterator[QueryRuntime]:
        retriever = ChunkRetriever(chunks_repo, embedding, collection)
        service = QueryService(retriever, EvidenceChecker(0.3), AnswerLlm(), LlmGate(2, 1.0), embedding.model_name,
                               s.default_top_k, 0.0, None, 100)
        live = None
        worker = None
        if live_enabled:
            signal = LiveSignal()
            judge = JudgeService(judge_llm, LlmCache(tmp_path / "judge.jsonl"), records, retriever, 2)
            worker = LiveJudgeWorker(judge, records, "cfg", s.default_top_k, 1.0,
                                     JudgeBudget(input_krw_per_mtok=1000.0, output_krw_per_mtok=5000.0, limit_krw=100.0), signal)
            recorder = LiveRecorder(records, "cfg", PRICE, signal, worker.enqueue)
            metrics = LiveMetricService(records, worker, "cfg", 0.3, "judge", {str(k): v for k, v in judge.versions.items()}, 100, 100.0)
            await worker.start()
            live = LiveEval(recorder=recorder, metrics=metrics, signal=signal)
        try:
            yield QueryRuntime(settings=s, service=service, repository=chunks_repo, collection=collection, contract=contract,
                               live=live)
        finally:
            if worker is not None:
                await worker.stop()

    with TestClient(create_app(settings, builder)) as client:
        yield client, records, judge_llm


def wait_for(client: TestClient, condition: str, value: int) -> dict[str, Any]:
    deadline = time.monotonic() + 5
    while True:
        snapshot: dict[str, Any] = client.get("/v1/metrics").json()
        if snapshot[condition] >= value or time.monotonic() > deadline:
            return snapshot
        time.sleep(0.05)


def test_answers_from_both_endpoints_are_recorded_judged_and_aggregated(tmp_path: Path) -> None:
    with serve(tmp_path) as (client, records, judge_llm):
        client.post("/v1/query", json={"question": "How do I move the uv cache?"}, headers={"X-Request-ID": "req-1"})
        client.post("/v1/query", json={"question": "How do I move the uv cache?"}, headers={"X-Request-ID": "req-1"})
        client.post("/v1/query/stream", json={"question": "Where is the uv cache directory?"}, headers={"X-Request-ID": "req-2"})
        client.post("/v1/query", json={"question": "What is the weather on Mars?", "top_k": 3})

        snapshot = wait_for(client, "judged", 2)

    assert sorted(records.rows) == ["live:req-1", "live:req-2"]
    assert snapshot["records"] == 2 and snapshot["answered"] == 2 and snapshot["judged"] == 2
    assert judge_llm.calls == 3
    metrics = {m["key"]: m for m in snapshot["metrics"]}
    assert metrics["refusal_rate"]["points"][-1]["cum"] == 0.0
    assert metrics["citation_precision"]["reference"] and metrics["citation_precision"]["points"][-1]["cum"] == 1.0
    assert snapshot["judge_spent_krw"] == round(4 * (1000 * 1000 / 1e6 + 100 * 5000 / 1e6), 1)


def test_metrics_are_unavailable_when_live_eval_is_off_but_queries_still_work(tmp_path: Path) -> None:
    with serve(tmp_path, live_enabled=False) as (client, records, _):
        answered = client.post("/v1/query", json={"question": "How do I move the uv cache?"})
        metrics = client.get("/v1/metrics")
        page = client.get("/dashboard")

    assert answered.status_code == 200 and records.rows == {}
    assert metrics.status_code == 503
    assert page.status_code == 200 and "실시간 평가 대시보드" in page.text
