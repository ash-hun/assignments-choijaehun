"""BM25 sparse 벡터 인코더. 문서 쪽에 단어 빈도 포화와 길이 정규화를 넣고, IDF는 벡터 DB(Qdrant IDF modifier)가 곱한다."""
import zlib
import statistics
from collections import Counter

from app.schema.vector_schema import SPARSE_DIM, SparseTerms
from app.common.text_tokenizer import TextTokenizer

# Robertson BM25의 통상값. 이 Corpus에 맞춰 조정하지 않는다(조정은 Part C 후보).
K1 = 1.2
B = 0.75


class Bm25Encoder:
    """토큰을 crc32로 SPARSE_DIM 공간에 해시한다. 어휘 사전이 없어 질의 쪽이 Corpus 상태 없이 같은 index를 만든다."""

    def __init__(self, tokenizer: TextTokenizer, k1: float = K1, b: float = B) -> None:
        self._tokenizer = tokenizer
        self._k1 = k1
        self._b = b

    @property
    def tokenizer(self) -> TextTokenizer:
        """이 인코더가 쓰는 토크나이저."""
        return self._tokenizer

    @staticmethod
    def hash_token(token: str) -> int:
        """토큰의 sparse index. 실행과 프로세스가 달라도 같은 값이 나오도록 내장 hash 대신 crc32를 쓴다."""
        return zlib.crc32(token.encode("utf-8")) % SPARSE_DIM

    def encode_documents(self, texts: list[str]) -> list[SparseTerms]:
        """문서 묶음 전체의 평균 길이로 정규화한다.

        평균 길이를 묶음 안에서 구하므로 Corpus 전체를 한 번에 넣어야 한다. Ingest는 매번 전체를 다시 색인한다.
        """
        tokenized = [self._tokenizer.tokenize(t) for t in texts]
        average = statistics.fmean(len(t) for t in tokenized) if tokenized else 0.0
        return [self._weigh(Counter(tokens), len(tokens), average) for tokens in tokenized]

    def encode_query(self, text: str) -> SparseTerms:
        """질의는 등장한 단어마다 1. 질의 안 반복은 무시해 긴 질문이 한 단어에 쏠리지 않게 한다."""
        indices = sorted({self.hash_token(t) for t in self._tokenizer.tokenize(text)})
        return SparseTerms(indices=indices, values=[1.0] * len(indices))

    def _weigh(self, counts: Counter[str], length: int, average: float) -> SparseTerms:
        norm = self._k1 * (1 - self._b + self._b * length / average) if average else self._k1
        weights: dict[int, float] = {}
        for token, tf in counts.items():
            # 해시 충돌은 두 단어의 가중치를 더한다. 2^20 공간에서 수만 어휘면 충돌은 드물다(실험 기록에 개수 기록).
            index = self.hash_token(token)
            weights[index] = weights.get(index, 0.0) + tf * (self._k1 + 1) / (tf + norm)
        indices = sorted(weights)
        return SparseTerms(indices=indices, values=[round(weights[i], 6) for i in indices])
