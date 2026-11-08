"""Chunking 선정 실험. 분할 설정마다 같은 임베딩으로 색인해 검색 지표, 근거 보존율, 질의당 근거 토큰 수를 잰다."""
import statistics
from pydantic import BaseModel
from difflib import SequenceMatcher

from app.service.eval.retrieval_metric import MetricSummary, RetrievalScore, paired_difference, score, summarize
from app.repository.qdrant_chunk_repository import QdrantChunkRepository
from app.service.eval.embedding_benchmark import EmbeddingBenchmark
from app.client.embedding_client import EmbeddingClient
from app.service.eval.evidence_matcher import normalize
from app.service.ingest.text_cleaner import clean_text
from app.schema.vector_schema import IndexContract
from app.schema.gold_schema import GoldItem
from app.schema.chunk_schema import Chunk
from app.common.logger import get_logger

# 생성 단계에 넣을 근거 수는 8단계에서 정한다. 그 전까지는 주 지표와 같은 상위 5개로 근거 토큰 수를 잰다.
CONTEXT_K = 5
# 경계에서 갈린 근거도 상위 k개 안에 조각이 모두 들어오면 생성 단계에서 온전히 쓸 수 있다. 이 비율을 k마다 잰다.
COVERAGE_KS = (5, 10)
MIN_COVER_CHARS = 20

logger = get_logger(__name__)


class ChunkingRun(BaseModel):
    """분할 설정 하나, 질의 언어 하나의 결과."""

    config: str
    language: str
    questions: int
    hit_at_5: MetricSummary
    hit_at_10: MetricSummary
    mrr_at_10: MetricSummary
    evidence_recall_at_10: MetricSummary
    doc_recall_at_5: MetricSummary
    by_type_hit_at_5: dict[str, float]
    chunks: int
    mean_tokens: float
    max_tokens: int
    evidence_preserved: float
    quotes_preserved: float
    context_tokens_mean: float
    evidence_covered_at_5: float
    evidence_covered_at_10: float
    split_seconds: float
    index_seconds: float
    per_question: list[RetrievalScore]


class ConfigVerdict(BaseModel):
    """판정 근거 한 줄. 1위 대비 Hit@5 짝지은 차이가 두 언어 모두 0을 포함하면 tied다."""

    config: str
    hit_at_5_diff: dict[str, MetricSummary]
    tied: bool
    evidence_preserved: float
    context_tokens_mean: float


class ChunkingVerdict(BaseModel):
    """Hit@5 1위, 1위와 차이 없는 후보, 그중 사전 규칙(근거 보존율, 근거 토큰 수)으로 고른 설정."""

    leader: str
    chosen: str
    rows: list[ConfigVerdict]


def evidence_preservation(items: list[GoldItem], chunks: list[Chunk]) -> tuple[float, float]:
    """(문항 비율, 구절 비율). 근거 구절이 같은 문서의 한 청크 안에 통째로 들어 있으면 보존된 것이다. 문항은 모든 구절이 보존돼야 한다."""
    texts: dict[str, list[str]] = {}
    for chunk in chunks:
        texts.setdefault(chunk.doc_id, []).append(normalize(chunk.text))
    answerable = [i for i in items if i.answerable]
    verdicts = [
        [any(normalize(clean_text(e.quote)) in text for text in texts.get(e.doc_id, [])) for e in item.evidence]
        for item in answerable
    ]
    quotes = [v for per_item in verdicts for v in per_item]
    return round(statistics.fmean(all(v) for v in verdicts), 4), round(statistics.fmean(quotes), 4)


def evidence_covered(item: GoldItem, ranked: list[Chunk], k: int) -> bool:
    """상위 k개 청크가 문항의 모든 근거 구절을 덮는지. 구절의 모든 글자가 같은 문서의 상위 k 청크 어딘가와 이어서 일치해야 한다.

    한 청크 안에 통째로 들어갔는지(근거 보존율)와 달리, 경계에서 갈린 구절도 조각이 모두 검색되면 덮인 것으로 본다.
    """
    top = [(c.doc_id, normalize(c.text)) for c in ranked[:k]]
    for evidence in item.evidence:
        quote = normalize(clean_text(evidence.quote))
        covered = [False] * len(quote)
        for doc, text in top:
            if doc != evidence.doc_id:
                continue
            matcher = SequenceMatcher(None, quote, text, autojunk=False)
            for block in matcher.get_matching_blocks():
                # 짧은 일치는 우연히 같은 낱말일 수 있어 세지 않는다.
                if block.size >= MIN_COVER_CHARS:
                    covered[block.a:block.a + block.size] = [True] * block.size
        # 청크 경계에서 잘려 나간 공백은 덮이지 않아도 된다.
        if not all(flag or ch == " " for flag, ch in zip(covered, quote)):
            return False
    return True


def pick_best(runs: list[ChunkingRun]) -> ChunkingVerdict:
    """Hit@5 우선. 1위와 두 언어 모두 차이가 없는 후보 중 근거 보존율이 높은 쪽, 같으면 근거 토큰 수가 적은 쪽, 그래도 같으면 먼저 온 쪽.

    runs의 설정 순서가 단순한 순서다.
    """
    configs = list(dict.fromkeys(r.config for r in runs))
    by_config = {c: {r.language: r for r in runs if r.config == c} for c in configs}

    def strength(config: str) -> tuple[float, float]:
        group = by_config[config].values()
        return statistics.fmean(r.hit_at_5.mean for r in group), statistics.fmean(r.mrr_at_10.mean for r in group)

    leader = max(configs, key=strength)
    rows = []
    for config in configs:
        diffs = {
            language: paired_difference(
                [float(s.hit_at_5) for s in by_config[leader][language].per_question],
                [float(s.hit_at_5) for s in run.per_question],
            )
            for language, run in by_config[config].items()
        }
        first = next(iter(by_config[config].values()))
        rows.append(ConfigVerdict(
            config=config, hit_at_5_diff=diffs, tied=all(d.ci_low <= 0 for d in diffs.values()),
            evidence_preserved=first.evidence_preserved, context_tokens_mean=first.context_tokens_mean,
        ))
    tied = [r for r in rows if r.tied]
    chosen = min(tied, key=lambda r: (-r.evidence_preserved, r.context_tokens_mean, configs.index(r.config)))
    return ChunkingVerdict(leader=leader, chosen=chosen.config, rows=rows)


class ChunkingBenchmark:
    """임베딩 모델은 고정하고 청크만 바꾼다. 색인과 정확 검색은 Embedding 선정 실험과 같은 코드를 쓴다."""

    def __init__(self, repository: QdrantChunkRepository, client: EmbeddingClient) -> None:
        self._repository = repository
        self._embedding = EmbeddingBenchmark(repository)
        self._client = client

    async def run(
        self, config: str, chunks: list[Chunk], items_by_language: dict[str, list[GoldItem]], split_seconds: float,
    ) -> list[ChunkingRun]:
        """설정 하나로 색인하고 언어별로 잰다. split_seconds는 호출자가 잰 분할 시간이다. 컬렉션은 시작할 때 지우고 끝나면 지운다."""
        tokens = {c.chunk_id: self._client.token_count(c.text) for c in chunks}
        collection = "chunk_" + config.replace("-", "_")
        contract = IndexContract(embedding_model=self._client.model_name, tokenizer="model-native", chunk_config_hash=config)
        index_seconds, _ = await self._embedding.index(self._client, collection, contract, chunks)
        preserved, quotes = evidence_preservation(next(iter(items_by_language.values())), chunks)

        runs = []
        for language, items in items_by_language.items():
            answerable = [i for i in items if i.answerable]
            ranked, _ = await self._embedding.search(self._client, collection, answerable, chunks)
            scores = [score(item, hits) for item, hits in zip(answerable, ranked)]
            context = [sum(tokens[c.chunk_id] for c in hits[:CONTEXT_K]) for hits in ranked]
            covered = {k: statistics.fmean(evidence_covered(i, hits, k) for i, hits in zip(answerable, ranked)) for k in COVERAGE_KS}
            runs.append(ChunkingRun(
                config=config, language=language, **summarize(scores).model_dump(),
                chunks=len(chunks), mean_tokens=round(statistics.fmean(tokens.values()), 1), max_tokens=max(tokens.values()),
                evidence_preserved=preserved, quotes_preserved=quotes,
                context_tokens_mean=round(statistics.fmean(context), 1),
                evidence_covered_at_5=round(covered[5], 4), evidence_covered_at_10=round(covered[10], 4), split_seconds=round(split_seconds, 1), index_seconds=round(index_seconds, 1),
                per_question=scores,
            ))
            logger.info("chunking_scored", config=config, language=language, hit_at_5=runs[-1].hit_at_5.mean, preserved=preserved)
        await self._repository.drop_collection(collection)
        return runs
