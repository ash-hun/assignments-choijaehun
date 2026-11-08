"""Embedding 선정 실험. 후보 모델마다 같은 청크를 색인하고 dev set(영어, 한국어)으로 근거 단위 검색 지표를 잰다."""
import time
from pydantic import BaseModel

from app.service.eval.retrieval_metric import MetricSummary, RetrievalScore, score, summarize
from app.repository.qdrant_chunk_repository import QdrantChunkRepository
from app.schema.vector_schema import SparseTerms, IndexContract
from app.client.embedding_client import EmbeddingClient
from app.schema.gold_schema import GoldItem
from app.schema.chunk_schema import Chunk
from app.common.logger import get_logger

TOP_K = 10

logger = get_logger(__name__)


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
        collection = "emb_" + "".join(ch if ch.isalnum() else "_" for ch in client.model_name.lower())
        contract = IndexContract(embedding_model=client.model_name, tokenizer="model-native", chunk_config_hash="fixed-1000")
        index_seconds, dim = await self.index(client, collection, contract, chunks)

        runs = []
        for language, items in items_by_language.items():
            answerable = [i for i in items if i.answerable]
            ranked, query_ms = await self.search(client, collection, answerable, chunks)
            scores = [score(item, hits) for item, hits in zip(answerable, ranked)]
            runs.append(_summarize(client.model_name, language, dim, scores, index_seconds, query_ms, token_counts, max_tokens))
            logger.info("embedding_scored", model=client.model_name, language=language, hit_at_5=runs[-1].hit_at_5.mean)
        await self._repository.drop_collection(collection)
        return runs

    async def index(self, client: EmbeddingClient, collection: str, contract: IndexContract, chunks: list[Chunk]) -> tuple[float, int]:
        """컬렉션을 지우고 새로 만들어 dense 벡터만 넣는다. 임베딩에 걸린 초와 벡터 차원을 돌려준다."""
        started = time.perf_counter()
        corpus = client.embed_documents([c.text for c in chunks])
        seconds = time.perf_counter() - started
        empty_sparse = [SparseTerms(indices=[], values=[]) for _ in chunks]
        await self._repository.drop_collection(collection)
        await self._repository.ensure_collection(collection, corpus.shape[1], contract)
        await self._repository.upsert(collection, chunks, corpus, empty_sparse)
        return seconds, int(corpus.shape[1])

    async def search(self, client: EmbeddingClient, collection: str, items: list[GoldItem], chunks: list[Chunk]) -> tuple[list[list[Chunk]], float]:
        """문항마다 정확 검색 상위 TOP_K 청크. 질의 임베딩의 문항당 평균 밀리초를 함께 돌려준다."""
        started = time.perf_counter()
        queries = client.embed_queries([i.question for i in items])
        query_ms = (time.perf_counter() - started) * 1000 / max(len(items), 1)
        by_id = {c.chunk_id: c for c in chunks}
        ranked = []
        for vector in queries:
            hits = await self._repository.search_dense(collection, vector, TOP_K, exact=True)
            ranked.append([by_id[h] for h in hits])
        return ranked, query_ms


def _summarize(
    model: str, language: str, dim: int, scores: list[RetrievalScore], index_seconds: float, query_ms: float,
    token_counts: list[int], max_tokens: int,
) -> EmbeddingRun:
    summary = summarize(scores)
    return EmbeddingRun(
        model=model, language=language, dim=dim, **summary.model_dump(),
        index_seconds=round(index_seconds, 1),
        query_ms_mean=round(query_ms, 1),
        max_chunk_tokens=max(token_counts),
        truncated_chunks=sum(1 for t in token_counts if t > max_tokens),
        per_question=scores,
    )
