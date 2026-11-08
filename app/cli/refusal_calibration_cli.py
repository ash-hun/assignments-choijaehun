"""거절 임계값 보정 실험 진입점. 확정 구성(Qwen3, structure-512-77)으로 색인하고 dev set 전 문항의 dense 최고 점수를 잰다."""
import sys
import json
import asyncio
from qdrant_client import AsyncQdrantClient

from app.cli.embedding_crosscheck_cli import CHUNK_METHOD, CHUNK_SIZE, CHUNK_OVERLAP, INCUMBENT, make_client
from app.service.eval.refusal_calibrator import TopScore, ThresholdVerdict, pick_threshold
from app.repository.qdrant_chunk_repository import QdrantChunkRepository
from app.service.eval.embedding_benchmark import EmbeddingBenchmark
from app.service.ingest.chunk_splitter import ChunkSplitter
from app.client.embedding_client import EmbeddingClient
from app.cli.chunking_selection_cli import load_corpus
from app.common.settings import Settings, get_settings
from app.cli.embedding_selection_cli import load_gold
from app.schema.vector_schema import IndexContract
from app.schema.gold_schema import GoldItem
from app.common.logger import get_logger

OUTPUT_DIR = "artifacts/refusal_threshold"
COLLECTION = "refusal_calibration"

logger = get_logger(__name__)


async def top_scores(
    repository: QdrantChunkRepository, client: EmbeddingClient, collection: str, gold: dict[str, list[GoldItem]], doc_of: dict[str, str],
) -> list[TopScore]:
    """답 있는 문항과 답 없는 문항 모두의 dense 최고 점수. 정확 검색이라 ANN 오차가 섞이지 않는다."""
    result = []
    for language, items in gold.items():
        vectors = client.embed_queries([i.question for i in items])
        for item, vector in zip(items, vectors):
            hits = await repository.search_dense_scored(collection, vector, 1, exact=True)
            chunk_id, score = hits[0]
            result.append(TopScore(item_id=str(item.id), language=language, type=item.type, answerable=item.answerable,
                                   score=round(score, 6), doc_id=doc_of[chunk_id]))
    return result


async def run(settings: Settings) -> list[TopScore]:
    """색인, 측정, 컬렉션 정리. 컬렉션은 시작할 때와 끝날 때 지운다."""
    documents = load_corpus(settings)
    gold = load_gold(settings)
    repository = QdrantChunkRepository(AsyncQdrantClient(url=settings.qdrant_url, prefer_grpc=True, timeout=60))
    client, _ = make_client(settings, INCUMBENT)
    splitter = ChunkSplitter(CHUNK_METHOD, CHUNK_SIZE, CHUNK_OVERLAP, client.token_count, client.token_offsets)
    chunks = [c for d in documents for c in splitter.split(d)]
    contract = IndexContract(embedding_model=client.model_name, tokenizer="model-native", chunk_config_hash=splitter.name)
    await EmbeddingBenchmark(repository).index(client, COLLECTION, contract, chunks)
    scores = await top_scores(repository, client, COLLECTION, gold, {c.chunk_id: c.doc_id for c in chunks})
    await repository.drop_collection(COLLECTION)
    return scores


def write(settings: Settings, scores: list[TopScore], verdict: ThresholdVerdict) -> None:
    """문항별 점수와 판정을 쓴다. 같은 결과면 같은 파일이 나온다."""
    out = settings.research_dir / OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)
    (out / "scores.jsonl").write_text("".join(s.model_dump_json() + "\n" for s in scores), encoding="utf-8")
    (out / "verdict.json").write_text(json.dumps(verdict.model_dump(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    logger.info("refusal_threshold_written", path=str(out), threshold=verdict.chosen.threshold)


def main() -> int:
    """측정하고 임계값을 고른다. 결과 파일은 매번 전부 덮어쓴다."""
    settings = get_settings()
    scores = asyncio.run(run(settings))
    write(settings, scores, pick_threshold(scores))
    return 0


if __name__ == "__main__":
    sys.exit(main())
