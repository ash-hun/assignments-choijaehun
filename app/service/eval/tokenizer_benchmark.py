"""토크나이저 선정 실험. 청크 길이 단위별 임베딩 토큰 수 관계와 BM25 토크나이저별 sparse 단독 검색 지표를 잰다."""
import time
import statistics
import numpy as np
from typing import Callable
from pydantic import BaseModel

from app.service.eval.retrieval_metric import MetricSummary, RetrievalScore, score, summarize
from app.repository.qdrant_chunk_repository import QdrantChunkRepository
from app.service.ingest.sparse_encoder import SparseEncoder
from app.schema.vector_schema import IndexContract
from app.schema.gold_schema import GoldItem
from app.schema.chunk_schema import Chunk
from app.common.logger import get_logger

TOP_K = 10
HANGUL_START, HANGUL_END = "가", "힣"

logger = get_logger(__name__)

LengthCounter = Callable[[str], int]


class RatioStats(BaseModel):
    """청크마다 구한 비율(단위 길이 / 기준 토큰 수)의 분포."""

    mean: float
    cv: float
    min: float
    p01: float
    max: float


class UnitLength(BaseModel):
    """한 분할 크기에서 길이 단위 하나의 측정값. 비율의 기준은 선정 임베딩의 토큰 수다."""

    window_chars: int
    unit: str
    chunks: int
    mean_length: float
    max_length: int
    ratio_to_reference: RatioStats


class CharLimitCheck(BaseModel):
    """문자 수 상한으로 목표 토큰 수를 맞추려 할 때 실제 임베딩 토큰 수가 어떻게 되는지."""

    target_tokens: int
    rule: str
    char_limit: int
    chunks: int
    over_target: float
    over_runner_up_cap: float
    mean_utilization: float
    max_tokens: int


class SparseRun(BaseModel):
    """BM25 토크나이저 하나, 질의 언어 하나의 sparse 단독 검색 결과."""

    tokenizer: str
    language: str
    questions: int
    hit_at_5: MetricSummary
    hit_at_10: MetricSummary
    mrr_at_10: MetricSummary
    evidence_recall_at_10: MetricSummary
    doc_recall_at_5: MetricSummary
    by_type_hit_at_5: dict[str, float]
    vocabulary: int
    hash_collisions: int
    tokenize_ms_per_1k_chunks: float
    query_token_coverage: float
    hangul_query_tokens: int
    hangul_tokens_in_corpus: int
    per_question: list[RetrievalScore]


def ratio_stats(values: list[float]) -> RatioStats:
    """비율 분포 요약. p01은 하위 1% 값으로, 문자 수 상한을 안전하게 잡을 때의 기준이다."""
    ordered = sorted(values)
    mean = statistics.fmean(ordered)
    return RatioStats(
        mean=round(mean, 4), cv=round(statistics.pstdev(ordered) / mean, 4), min=round(ordered[0], 4),
        p01=round(ordered[int(0.01 * (len(ordered) - 1))], 4), max=round(ordered[-1], 4),
    )


def measure_units(window_chars: int, chunks: list[Chunk], counters: dict[str, LengthCounter], reference: str) -> list[UnitLength]:
    """같은 청크를 단위마다 재고 기준 단위(임베딩 토큰)와의 비율 분포를 낸다."""
    lengths = {unit: [count(c.text) for c in chunks] for unit, count in counters.items()}
    base = lengths[reference]
    return [
        UnitLength(
            window_chars=window_chars, unit=unit, chunks=len(chunks), mean_length=round(statistics.fmean(values), 1),
            max_length=max(values), ratio_to_reference=ratio_stats([v / r for v, r in zip(values, base)]),
        )
        for unit, values in lengths.items()
    ]


def check_char_limit(
    target: int, rule: str, char_limit: int, chunks: list[Chunk], count: LengthCounter, runner_up: LengthCounter, runner_up_cap: int,
) -> CharLimitCheck:
    """char_limit으로 자른 청크의 실제 임베딩 토큰 수를 목표와 2위 모델 최대 입력에 대어 본다."""
    tokens = [count(c.text) for c in chunks]
    runner = [runner_up(c.text) for c in chunks]
    return CharLimitCheck(
        target_tokens=target, rule=rule, char_limit=char_limit, chunks=len(chunks),
        over_target=round(sum(t > target for t in tokens) / len(tokens), 4),
        over_runner_up_cap=round(sum(t > runner_up_cap for t in runner) / len(runner), 4),
        mean_utilization=round(statistics.fmean(tokens) / target, 4), max_tokens=max(tokens),
    )


class TokenizerBenchmark:
    """sparse 검색은 Qdrant에서 항상 전수 계산이라 ANN 오차가 섞이지 않는다."""

    def __init__(self, repository: QdrantChunkRepository) -> None:
        self._repository = repository

    async def run_sparse(self, encoder: SparseEncoder, chunks: list[Chunk], items_by_language: dict[str, list[GoldItem]]) -> list[SparseRun]:
        """후보 토크나이저 하나로 색인하고 언어별 질의로 sparse 단독 검색을 잰다."""
        tokenizer = encoder.tokenizer
        started = time.perf_counter()
        doc_tokens = [tokenizer.tokenize(c.text) for c in chunks]
        tokenize_ms = (time.perf_counter() - started) * 1000 * 1000 / len(chunks)
        vocabulary = {t for tokens in doc_tokens for t in tokens}
        hashes = {SparseEncoder.hash_token(t) for t in vocabulary}
        sparse = encoder.encode_documents([c.text for c in chunks])

        collection = "tok_" + tokenizer.name.replace("+", "_")
        contract = IndexContract(embedding_model="none", tokenizer=tokenizer.name, chunk_config_hash="fixed-1000")
        await self._repository.drop_collection(collection)
        # dense 벡터 자리는 필수라 1차원 상수 벡터를 넣는다. 이 실험은 sparse만 검색한다.
        await self._repository.ensure_collection(collection, 1, contract)
        await self._repository.upsert(collection, chunks, np.ones((len(chunks), 1), dtype=np.float32), sparse)
        by_id = {c.chunk_id: c for c in chunks}

        runs = []
        for language, items in items_by_language.items():
            answerable = [i for i in items if i.answerable]
            query_tokens = [t for i in answerable for t in tokenizer.tokenize(i.question)]
            hangul = [t for t in query_tokens if HANGUL_START <= t[0] <= HANGUL_END]
            scores = []
            for item in answerable:
                hits = await self._repository.search_sparse(collection, encoder.encode_query(item.question), TOP_K)
                scores.append(score(item, [by_id[h] for h in hits]))
            summary = summarize(scores)
            runs.append(SparseRun(
                tokenizer=tokenizer.name, language=language, **summary.model_dump(),
                vocabulary=len(vocabulary), hash_collisions=len(vocabulary) - len(hashes),
                tokenize_ms_per_1k_chunks=round(tokenize_ms, 1),
                query_token_coverage=round(sum(t in vocabulary for t in query_tokens) / max(len(query_tokens), 1), 4),
                hangul_query_tokens=len(hangul), hangul_tokens_in_corpus=sum(t in vocabulary for t in hangul),
                per_question=scores,
            ))
            logger.info("sparse_scored", tokenizer=tokenizer.name, language=language, hit_at_5=summary.hit_at_5.mean)
        await self._repository.drop_collection(collection)
        return runs

