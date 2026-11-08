"""지표 타당성 검증용으로 일부러 망가뜨린 파이프라인 부품. 지표가 이 변형에서 실제로 떨어지는지 본다."""
import re
import random

from app.service.query.evidence_checker import EvidenceChecker
from app.service.query.chunk_retriever import ChunkRetriever
from app.schema.query_schema import RetrievedChunk
from app.schema.chunk_schema import Chunk

CITATION = re.compile(r"\[(\d+)\]")


class RandomChunkRetriever(ChunkRetriever):
    """질문과 관계없는 청크를 돌려준다. 질문과 seed가 같으면 같은 청크라 Judge가 같은 근거를 다시 볼 수 있다."""

    def __init__(self, chunks: list[Chunk], seed: int) -> None:
        self._pool = sorted(chunks, key=lambda c: c.chunk_id)
        self._seed = seed

    async def retrieve(self, question: str, k: int) -> list[RetrievedChunk]:
        """점수는 1.0이라 검색 단계 거절을 통과한다."""
        rng = random.Random(f"{self._seed}:{question}")
        return [RetrievedChunk(chunk=c, score=1.0) for c in rng.sample(self._pool, min(k, len(self._pool)))]


class NeverRefuseChecker(EvidenceChecker):
    """검색 점수와 근거 부족 토큰을 모두 무시해 거절하지 않는다."""

    def __init__(self) -> None:
        super().__init__(threshold=0.0)

    def has_evidence(self, top_dense_score: float | None) -> bool:
        """항상 근거가 있다고 본다."""
        return True

    def is_insufficient(self, answer: str) -> bool:
        """근거 부족 토큰도 답으로 내보낸다."""
        return False


def strip_citations(answer: str) -> str:
    """[n] 인용을 모두 지운다. 사실 문장마다 인용을 요구하는 항목이 이 변형에서 떨어져야 한다."""
    return CITATION.sub("", answer)


def shuffle_citations(answer: str, context_size: int) -> str:
    """[n]을 [n % context_size + 1]로 바꿔 모든 인용이 다른 근거를 가리키게 한다."""
    return CITATION.sub(lambda m: f"[{int(m.group(1)) % context_size + 1}]", answer)
