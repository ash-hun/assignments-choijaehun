"""query 기능의 HTTP 통합 테스트. 실제 앱(라우터, 미들웨어, 인증, 에러 매핑)에 메모리 저장소, 임베딩, 대체 LLM을 넣어 돌린다."""
import json
import asyncio
from typing import Any
from pydantic import SecretStr
from fastapi.testclient import TestClient
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager

from tests.integ.memory_backend import MemoryChunkRepository, MemoryEmbeddingClient
from app.client.llm_client import LlmDelta, ChatMessage, LlmClient, LlmCompletion
from app.service.query.chunk_retriever import FusionSettings, ChunkRetriever
from app.common.upstream_error import LlmFailureError, LlmTimeoutError
from app.service.query.prompt_builder import INSUFFICIENT_CONTEXT
from app.service.query.evidence_checker import EvidenceChecker
from app.service.ingest.sparse_encoder import SparseEncoder
from app.service.query.query_service import QueryService
from app.common.text_tokenizer import TextTokenizer
from app.schema.query_schema import RetrievalMode
from app.service.query.llm_gate import LlmGate
from app.api.query_runtime import QueryRuntime
from app.schema.chunk_schema import Chunk
from app.common.settings import Settings
from app.main import create_app

CACHE = "The cache directory defaults to the user cache folder and can be moved with UV_CACHE_DIR."
LOCK = "The lockfile records exact resolved versions so installs are reproducible across machines."


class ScriptedLlm(LlmClient):
    def __init__(self) -> None:
        self.failure: Exception | None = None

    @property
    def model(self) -> str:
        return "scripted"

    async def complete(self, messages: list[ChatMessage], seed: int | None, max_completion_tokens: int,
                       temperature: float | None = None, json_schema: dict[str, Any] | None = None) -> LlmCompletion:
        if self.failure:
            raise self.failure
        return LlmCompletion(text=self._text(messages), model="scripted", input_tokens=40, output_tokens=6)

    async def stream(self, messages: list[ChatMessage], seed: int | None, max_completion_tokens: int,
                     temperature: float | None = None, json_schema: dict[str, Any] | None = None) -> AsyncIterator[LlmDelta | LlmCompletion]:
        text = self._text(messages)
        for piece in text.split(" "):
            yield LlmDelta(text=piece + " ")
            if self.failure:
                raise self.failure
        yield LlmCompletion(text=text, model="scripted", input_tokens=40, output_tokens=6)

    @staticmethod
    def _text(messages: list[ChatMessage]) -> str:
        return INSUFFICIENT_CONTEXT if "lockfile" in messages[-1].content.split("<question>")[1] else "Set UV_CACHE_DIR [1]."


@contextmanager
def serve(api_key: str | None = None, mode: RetrievalMode = "dense") -> Iterator[tuple[TestClient, MemoryChunkRepository, ScriptedLlm]]:
    settings = Settings(_env_file=None, api_key=SecretStr(api_key) if api_key else None)
    contract = settings.index_contract()
    collection = contract.collection_name(settings.corpus_name)
    repository, embedding, llm = MemoryChunkRepository(), MemoryEmbeddingClient(), ScriptedLlm()
    chunks = [Chunk(chunk_id=Chunk.make_id(d, t), doc_id=d, ordinal=0, text=t, title=d, url=f"https://example/{d}")
              for d, t in (("cache.md", CACHE), ("lock.md", LOCK))]

    async def index() -> None:
        await repository.ensure_collection(collection, 256, contract)
        await repository.upsert(collection, chunks, embedding.embed_documents([c.text for c in chunks]),
                                encoder.encode_documents([c.text for c in chunks]))

    encoder = SparseEncoder(TextTokenizer("word"))
    asyncio.run(index())

    @asynccontextmanager
    async def builder(s: Settings) -> AsyncIterator[QueryRuntime]:
        retriever = ChunkRetriever(repository, embedding, collection, encoder, FusionSettings(mode=mode, pool=4))
        service = QueryService(retriever, EvidenceChecker(0.3), llm, LlmGate(2, 0.1),
                               embedding.model_name, 2, 0.0, None, 100)
        yield QueryRuntime(settings=s, service=service, repository=repository, collection=collection, contract=contract)

    with TestClient(create_app(settings, builder)) as client:
        yield client, repository, llm


def test_answer_has_citation_sources_and_echoes_a_valid_request_id() -> None:
    with serve() as (client, _, _):
        response = client.post("/v1/query", json={"question": "Where is the cache directory UV_CACHE_DIR?"}, headers={"X-Request-ID": "req-1"})

    body = response.json()
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-1"
    assert body["status"] == "answered"
    assert body["citations"][0]["doc_id"] == "cache.md"
    assert body["citations"][0]["url"] == "https://example/cache.md"
    assert body["meta"]["usage"] == {"input_tokens": 40, "output_tokens": 6}


def test_off_topic_and_token_refusals_return_200_insufficient_context() -> None:
    with serve() as (client, _, _):
        off_topic = client.post("/v1/query", json={"question": "kubernetes autoscaler replicas"}).json()
        token = client.post("/v1/query", json={"question": "Why does the lockfile record exact resolved versions?"}).json()

    assert (off_topic["status"], off_topic["meta"]["usage"]["input_tokens"]) == ("insufficient_context", 0)
    assert (token["status"], token["meta"]["usage"]["input_tokens"]) == ("insufficient_context", 40)


def test_invalid_body_api_key_and_bad_request_id_are_handled_at_the_boundary() -> None:
    with serve(api_key="secret") as (client, _, _):
        missing = client.post("/v1/query", json={"question": "cache"})
        wrong = client.post("/v1/query", json={"question": "cache"}, headers={"X-API-Key": "nope"})
        empty = client.post("/v1/query", json={"question": ""}, headers={"X-API-Key": "secret"})
        health = client.get("/health", headers={"X-Request-ID": "bad id\nINJECT"})

    assert (missing.status_code, wrong.status_code, empty.status_code, health.status_code) == (401, 401, 422, 200)
    assert len(health.headers["X-Request-ID"]) == 32


def test_upstream_failures_map_to_502_503_504_without_internal_details() -> None:
    with serve() as (client, repository, llm):
        llm.failure = LlmTimeoutError("llm request timed out")
        timeout = client.post("/v1/query", json={"question": "cache directory UV_CACHE_DIR"})
        llm.failure = LlmFailureError("llm request failed")
        failure = client.post("/v1/query", json={"question": "cache directory UV_CACHE_DIR"})
        repository.down = True
        store = client.post("/v1/query", json={"question": "cache directory UV_CACHE_DIR"})
        ready = client.get("/ready")

    assert (timeout.status_code, failure.status_code, store.status_code, ready.status_code) == (504, 502, 503, 503)
    assert store.json() == {"detail": "vector store unavailable"}


def test_ready_reports_the_collection_when_the_contract_matches() -> None:
    with serve() as (client, _, _):
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["collection"].startswith("chunks_uv_docs_")


def events(body: str) -> list[tuple[str, dict[str, Any]]]:
    frames = [f for f in body.split("\n\n") if f.strip()]
    parsed = []
    for frame in frames:
        name, data = frame.split("\n", 1)
        parsed.append((name.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return parsed


def test_stream_sends_tokens_then_final_with_the_same_citations_as_the_json_endpoint() -> None:
    question = {"question": "Where is the cache directory UV_CACHE_DIR?"}
    with serve() as (client, _, _):
        stream = client.post("/v1/query/stream", json=question)
        plain = client.post("/v1/query", json=question).json()

    parsed = events(stream.text)
    assert stream.headers["content-type"].startswith("text/event-stream")
    assert [name for name, _ in parsed[:-1]] == ["token"] * (len(parsed) - 1) and parsed[-1][0] == "final"
    assert parsed[-1][1]["citations"] == plain["citations"]
    assert parsed[-1][1]["meta"]["first_token_ms"] is not None


def test_stream_refused_by_score_sends_only_final_and_mid_stream_failure_sends_error() -> None:
    with serve() as (client, _, llm):
        refused = events(client.post("/v1/query/stream", json={"question": "kubernetes autoscaler replicas"}).text)
        llm.failure = LlmTimeoutError("llm request timed out")
        broken = events(client.post("/v1/query/stream", json={"question": "cache directory UV_CACHE_DIR"}).text)

    assert [name for name, _ in refused] == ["final"]
    assert refused[0][1]["status"] == "insufficient_context"
    assert broken[0][0] == "token"
    assert broken[-1] == ("error", {"detail": "llm request timed out", "status_code": 504})


def test_stream_failure_before_the_first_event_is_a_plain_http_error() -> None:
    with serve() as (client, repository, _):
        repository.down = True
        response = client.post("/v1/query/stream", json={"question": "cache directory UV_CACHE_DIR"})

    assert (response.status_code, response.json()) == (503, {"detail": "vector store unavailable"})


def test_every_retrieval_mode_answers_from_the_same_source_and_refuses_by_the_same_dense_score() -> None:
    results = {}
    for mode in ("dense", "bm25", "rrf", "cc"):
        with serve(mode=mode) as (client, _, _):
            answered = client.post("/v1/query", json={"question": "Where is the cache directory UV_CACHE_DIR?"}).json()
            refused = client.post("/v1/query", json={"question": "kubernetes autoscaler replicas"}).json()
        results[mode] = (answered, refused)

    dense_top = results["dense"][0]["meta"]["top_dense_score"]
    for mode, (answered, refused) in results.items():
        assert answered["citations"][0]["doc_id"] == "cache.md", mode
        assert answered["meta"]["top_dense_score"] == dense_top, mode
        assert (refused["status"], refused["meta"]["usage"]["input_tokens"]) == ("insufficient_context", 0), mode
    assert results["bm25"][0]["meta"]["retrieval_scores"] != results["dense"][0]["meta"]["retrieval_scores"]
