"""시맨틱 분할에 쓰는 문장 임베딩. 같은 문장은 한 번만 임베딩해 여러 분할 설정이 결과를 나눠 쓴다."""
import numpy as np

from app.client.embedding_client import EmbeddingClient


class SentenceEmbedder:
    """시맨틱 분할의 문장 임베딩. 크기만 바꾼 설정끼리 같은 문장이 반복되므로 텍스트별로 한 번만 임베딩한다."""

    def __init__(self, client: EmbeddingClient) -> None:
        self._client = client
        self._cache: dict[str, np.ndarray] = {}

    def __call__(self, texts: list[str]) -> np.ndarray:
        """입력 순서대로 L2 정규화된 벡터."""
        missing = [t for t in dict.fromkeys(texts) if t not in self._cache]
        if missing:
            self._cache.update(zip(missing, self._client.embed_documents(missing)))
        return np.stack([self._cache[t] for t in texts])
