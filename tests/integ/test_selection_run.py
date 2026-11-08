"""selection_run 기능의 선정 파이프라인 통합 테스트(Chunking, Embedding 교차 확인, 거절 임계값, LLM). 분할, 색인, 검색, 생성, 지표, 판정을 이어서 돌린다."""
import asyncio
from typing import Any
from pathlib import Path

from app.service.eval.llm_benchmark import LlmAnswer, LlmBenchmark, LlmCandidate, RetrievedItem, summarize_llm
from app.service.eval.chunking_benchmark import ChunkingRun, ChunkingBenchmark, pick_best
from app.service.eval.embedding_crosscheck import ModelResult, judge, truncated_chunks
from tests.integ.memory_backend import MemoryChunkRepository, MemoryEmbeddingClient
from app.service.eval.refusal_calibrator import TopScore, pick_threshold
from app.service.ingest.chunk_splitter import ChunkMethod, ChunkSplitter
from app.client.llm_client import ChatMessage, LlmClient, LlmCompletion
from app.service.eval.embedding_benchmark import EmbeddingBenchmark
from app.service.ingest.sentence_embedder import SentenceEmbedder
from app.service.query.prompt_builder import INSUFFICIENT_CONTEXT
from app.service.query.evidence_checker import EvidenceChecker
from app.schema.gold_schema import GoldItem, GoldEvidence
from app.cli.refusal_calibration_cli import top_scores
from app.schema.chunk_schema import Chunk, Document
from app.schema.vector_schema import IndexContract
from app.client.llm_cache import LlmCache

CACHE = "The cache directory defaults to the user cache folder and can be moved with UV_CACHE_DIR."
LOCK = "The lockfile records exact resolved versions so installs are reproducible across machines."
DOCUMENTS = [
    Document(doc_id="cache.md", title="Cache", text=f"# Cache\n\nIntro text about caching.\n\n## Location\n\n{CACHE}\n"),
    Document(doc_id="lock.md", title="Lock", text=f"# Lockfile\n\nIntro text about locking.\n\n## Purpose\n\n{LOCK}\n"),
]


def gold(language: str) -> list[GoldItem]:
    questions = {"en": ("Where is the cache directory?", "Why does the lockfile record resolved versions?"),
                 "ko": ("cache directory 위치는?", "lockfile 이 resolved versions 를 기록하는 이유는?")}[language]
    items = []
    for ordinal, (question, doc_id, quote) in enumerate(zip(questions, ("cache.md", "lock.md"), (CACHE, LOCK)), start=1):
        source = GoldItem.make_id("dev", "factual", ordinal)
        items.append(GoldItem(
            id=source if language == "en" else GoldItem.make_translation_id(source, "ko"), split="dev", type="factual",
            question=question, answerable=True, reference_answer="a", evidence=[GoldEvidence(doc_id=doc_id, quote=quote)],
            origin="llm_draft_reviewed", language=language, translation_of=None if language == "en" else source,
        ))
    return items


def run_pipeline(methods: tuple[ChunkMethod, ...]) -> tuple[list[ChunkingRun], MemoryChunkRepository, MemoryEmbeddingClient]:
    client = MemoryEmbeddingClient()
    repository = MemoryChunkRepository()
    benchmark = ChunkingBenchmark(repository, client)
    embedder = SentenceEmbedder(client)
    items = {"en": gold("en"), "ko": gold("ko")}

    async def measure() -> list[ChunkingRun]:
        runs: list[ChunkingRun] = []
        for method in methods:
            splitter = ChunkSplitter(method, 40, 0, client.token_count, client.token_offsets, embedder if method == "semantic" else None)
            chunks = [c for d in DOCUMENTS for c in splitter.split(d)]
            runs += await benchmark.run(splitter.name, chunks, items, 0.0)
        return runs

    return asyncio.run(measure()), repository, client


def test_chunking_selection_finds_whole_evidence_and_picks_the_simplest_tied_method() -> None:
    runs, repository, _ = run_pipeline(("fixed", "structure", "semantic"))

    assert all(r.hit_at_5.mean == 1.0 and r.evidence_preserved == 1.0 for r in runs)
    assert repository.collections == {}
    verdict = pick_best(runs)
    assert all(row.tied for row in verdict.rows)
    assert verdict.chosen == min(verdict.rows, key=lambda r: (r.context_tokens_mean, ["fixed", "structure", "semantic"].index(r.config.split("-")[0]))).config


def test_rerunning_the_pipeline_gives_the_same_judgements() -> None:
    first, _, _ = run_pipeline(("fixed", "semantic"))
    second, _, _ = run_pipeline(("fixed", "semantic"))

    assert [r.per_question for r in first] == [r.per_question for r in second]
    assert [(r.chunks, r.context_tokens_mean) for r in first] == [(r.chunks, r.context_tokens_mean) for r in second]


class ShortMemoryEmbeddingClient(MemoryEmbeddingClient):
    @property
    def model_name(self) -> str:
        return "memory-short"


def test_embedding_crosscheck_counts_truncation_and_judges_tied_models_by_coverage() -> None:
    repository = MemoryChunkRepository()
    incumbent, challenger = MemoryEmbeddingClient(), ShortMemoryEmbeddingClient()
    splitter = ChunkSplitter("structure", 40, 0, incumbent.token_count, incumbent.token_offsets)
    chunks = [c for d in DOCUMENTS for c in splitter.split(d)]
    items = {"en": gold("en"), "ko": gold("ko")}

    async def measure() -> tuple[ModelResult, ModelResult]:
        results = []
        for client, limit in ((incumbent, 40), (challenger, 10)):
            runs = await ChunkingBenchmark(repository, client).run(splitter.name, chunks, items, 0.0)
            results.append(ModelResult(model=client.model_name, max_input_tokens=limit,
                                       truncated_chunks=truncated_chunks(client, chunks, limit), runs=runs))
        return results[0], results[1]

    first, second = asyncio.run(measure())
    verdict = judge(first, second)

    assert (first.truncated_chunks, second.truncated_chunks > 0) == (0, True)
    assert (verdict.chosen, verdict.reason) == ("memory-short", "tied_challenger_cheaper")
    assert repository.collections == {}


def test_refusal_calibration_scores_every_item_and_keeps_answerable_items_above_the_threshold() -> None:
    repository = MemoryChunkRepository()
    client = MemoryEmbeddingClient()
    splitter = ChunkSplitter("structure", 40, 0, client.token_count, client.token_offsets)
    chunks = [c for d in DOCUMENTS for c in splitter.split(d)]
    unanswerable = GoldItem(
        id=GoldItem.make_id("dev", "unanswerable", 1), split="dev", type="unanswerable", question="Kubernetes autoscaler replicas?",
        answerable=False, reference_answer="", evidence=[], origin="llm_draft_reviewed",
    )
    items = {"en": gold("en") + [unanswerable]}

    async def measure() -> list[TopScore]:
        contract = IndexContract(embedding_model=client.model_name, tokenizer="model-native", chunk_config_hash=splitter.name)
        await EmbeddingBenchmark(repository).index(client, "calib", contract, chunks)
        return await top_scores(repository, client, "calib", items, {c.chunk_id: c.doc_id for c in chunks})

    scores = asyncio.run(measure())
    verdict = pick_threshold(scores)

    assert len(scores) == 3
    assert [s.doc_id for s in scores if s.answerable] == ["cache.md", "lock.md"]
    assert verdict.chosen.false_refusal == {"en": 0.0}
    assert verdict.chosen.unanswerable_refused == {"en": 1.0}


class ScriptedLlmClient(LlmClient):
    def __init__(self) -> None:
        self.calls = 0

    @property
    def model(self) -> str:
        return "scripted"

    async def complete(self, messages: list[ChatMessage], seed: int | None, max_completion_tokens: int,
                       temperature: float | None = None, json_schema: dict[str, Any] | None = None) -> LlmCompletion:
        self.calls += 1
        text = INSUFFICIENT_CONTEXT if "Kubernetes" in messages[-1].content else "Set UV_CACHE_DIR [1][7]."
        return LlmCompletion(text=text, model="scripted", input_tokens=100, output_tokens=10)


def test_llm_selection_refuses_by_score_then_token_and_reuses_cached_answers(tmp_path: Path) -> None:
    chunks = [Chunk(chunk_id=Chunk.make_id("cache.md", CACHE), doc_id="cache.md", ordinal=0, text=CACHE)]
    items = [
        RetrievedItem(item_id="a", language="en", type="factual", answerable=True, question="Where is the cache?", top_score=0.9, chunks=chunks),
        RetrievedItem(item_id="b", language="en", type="unanswerable", answerable=False, question="Kubernetes HPA?", top_score=0.9, chunks=chunks),
        RetrievedItem(item_id="c", language="en", type="unanswerable", answerable=False, question="Nexus policy?", top_score=0.1, chunks=chunks),
    ]
    candidate = LlmCandidate(name="scripted", input_krw_per_mtok=1000.0, output_krw_per_mtok=4000.0, temperature=None, seeds=[42])
    llm = ScriptedLlmClient()

    def measure() -> list[LlmAnswer]:
        benchmark = LlmBenchmark(EvidenceChecker(0.5), LlmCache(tmp_path / "responses.jsonl"), 2)
        return asyncio.run(benchmark.run(llm, candidate, items))

    first = measure()
    second = measure()
    [summary] = summarize_llm(candidate, first)

    assert llm.calls == 2
    assert [(a.stage, a.refused) for a in first] == [("generation", False), ("generation", True), ("retrieval", True)]
    assert (first[0].citations, first[0].dropped_citations) == ([1], 1)
    assert (summary.format_compliance, summary.dropped_citation_rate, summary.unanswerable_refusal) == (1.0, 0.5, 1.0)
    assert summary.cost_krw_per_item == round((2 * 100 * 1000 + 2 * 10 * 4000) / 1e6 / 3, 4)
    assert [a.model_dump(exclude={"latency_ms"}) for a in first] == [a.model_dump(exclude={"latency_ms"}) for a in second]
