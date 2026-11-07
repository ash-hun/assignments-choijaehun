"""Embedding 선정 실험. 후보 모델마다 같은 청크를 색인하고 dev set(영어, 한국어)으로 근거 단위 검색 지표를 잰다."""
import time
import random
import statistics
from pydantic import BaseModel

from app.repository.qdrant_chunk_repository import QdrantChunkRepository
from app.service.eval.retrieval_metric import RetrievalScore, score
from app.schema.vector_schema import SparseTerms, IndexContract
from app.client.embedding_client import EmbeddingClient
from app.schema.gold_schema import GoldItem
from app.schema.chunk_schema import Chunk
from app.common.logger import get_logger

TOP_K = 10
BOOTSTRAP_SAMPLES = 2000
BOOTSTRAP_SEED = 2026

logger = get_logger(__name__)


class MetricSummary(BaseModel):
    """지표 하나의 평균과 문항 bootstrap 95% 신뢰구간."""

    mean: float
    ci_low: float
    ci_high: float


class EmbeddingRun(BaseModel):
    """후보 모델 하나, 질의 언어 하나의 결과."""

    model: str
    language: str
    dim: int
    questions: int
    hit_at_5: MetricSummary
    hit_at_10: MetricSummary
    mrr_at_10: MetricSummary
    evidence_recall_at_10: MetricSummary
    doc_recall_at_5: MetricSummary
    by_type_hit_at_5: dict[str, float]
    index_seconds: float
    query_ms_mean: float
    max_chunk_tokens: int
    truncated_chunks: int
    per_question: list[RetrievalScore]


class EmbeddingBenchmark:
    """선정된 DB(Qdrant)의 정확 검색 모드로 재서 ANN 오차가 모델 비교에 섞이지 않게 한다."""

    def __init__(self, repository: QdrantChunkRepository) -> None:
        self._repository = repository

    async def run(
        self, client: EmbeddingClient, max_tokens: int, chunks: list[Chunk], items_by_language: dict[str, list[GoldItem]],
    ) -> list[EmbeddingRun]:
        """색인은 모델마다 한 번, 질의는 언어별로 따로 잰다."""
        token_counts = [client.token_count(c.text) for c in chunks]
        started = time.perf_counter()
        corpus = client.embed_documents([c.text for c in chunks])
        index_seconds = time.perf_counter() - started

        collection = "emb_" + "".join(ch if ch.isalnum() else "_" for ch in client.model_name.lower())
        contract = IndexContract(embedding_model=client.model_name, tokenizer="model-native", chunk_config_hash="fixed-1000")
        empty_sparse = [SparseTerms(indices=[], values=[]) for _ in chunks]
        await self._repository.drop_collection(collection)
        await self._repository.ensure_collection(collection, corpus.shape[1], contract)
        await self._repository.upsert(collection, chunks, corpus, empty_sparse)
        by_id = {c.chunk_id: c for c in chunks}

        runs = []
        for language, items in items_by_language.items():
            answerable = [i for i in items if i.answerable]
            started = time.perf_counter()
            queries = client.embed_queries([i.question for i in answerable])
            query_ms = (time.perf_counter() - started) * 1000 / max(len(answerable), 1)
            scores = []
            for item, vector in zip(answerable, queries):
                hits = await self._repository.search_dense(collection, vector, TOP_K, exact=True)
                scores.append(score(item, [by_id[h] for h in hits]))
            runs.append(_summarize(client.model_name, language, corpus.shape[1], scores, index_seconds, query_ms, token_counts, max_tokens))
            logger.info("embedding_scored", model=client.model_name, language=language, hit_at_5=runs[-1].hit_at_5.mean)
        await self._repository.drop_collection(collection)
        return runs


def bootstrap(values: list[float]) -> MetricSummary:
    """문항을 복원 추출해 평균의 95% 구간을 구한다. seed가 고정이라 같은 입력이면 같은 구간이다."""
    rng = random.Random(BOOTSTRAP_SEED)
    means = sorted(statistics.fmean(rng.choices(values, k=len(values))) for _ in range(BOOTSTRAP_SAMPLES))
    return MetricSummary(
        mean=round(statistics.fmean(values), 4),
        ci_low=round(means[int(0.025 * BOOTSTRAP_SAMPLES)], 4),
        ci_high=round(means[int(0.975 * BOOTSTRAP_SAMPLES) - 1], 4),
    )


def paired_difference(a: list[float], b: list[float]) -> MetricSummary:
    """같은 문항에 대한 두 모델 점수 차(a - b)의 평균과 95% 구간. 구간이 0을 포함하면 차이 없음으로 본다."""
    return bootstrap([x - y for x, y in zip(a, b)])


def _summarize(
    model: str, language: str, dim: int, scores: list[RetrievalScore], index_seconds: float, query_ms: float,
    token_counts: list[int], max_tokens: int,
) -> EmbeddingRun:
    by_type: dict[str, list[float]] = {}
    for s in scores:
        by_type.setdefault(s.type, []).append(float(s.hit_at_5))
    return EmbeddingRun(
        model=model, language=language, dim=dim, questions=len(scores),
        hit_at_5=bootstrap([float(s.hit_at_5) for s in scores]),
        hit_at_10=bootstrap([float(s.hit_at_10) for s in scores]),
        mrr_at_10=bootstrap([s.reciprocal_rank for s in scores]),
        evidence_recall_at_10=bootstrap([s.evidence_recall_at_10 for s in scores]),
        doc_recall_at_5=bootstrap([float(s.doc_recall_at_5) for s in scores]),
        by_type_hit_at_5={t: round(statistics.fmean(v), 4) for t, v in sorted(by_type.items())},
        index_seconds=round(index_seconds, 1),
        query_ms_mean=round(query_ms, 1),
        max_chunk_tokens=max(token_counts),
        truncated_chunks=sum(1 for t in token_counts if t > max_tokens),
        per_question=scores,
    )
