"""ingest 기능의 시맨틱 분할용 문장 임베딩 캐시(SentenceEmbedder) 단위 테스트."""
import numpy as np

from app.service.ingest.sentence_embedder import SentenceEmbedder
from app.client.embedding_client import EmbeddingClient


class CountingClient(EmbeddingClient):
    def __init__(self) -> None:
        self.embedded: list[list[str]] = []

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        self.embedded.append(texts)
        return np.array([[float(len(t)), 1.0] for t in texts])


def test_each_distinct_sentence_is_embedded_once_and_order_is_kept() -> None:
    client = CountingClient()
    embedder = SentenceEmbedder(client)

    first = embedder(["aa", "b", "aa"])
    second = embedder(["b", "ccc"])

    assert client.embedded == [["aa", "b"], ["ccc"]]
    assert first[:, 0].tolist() == [2.0, 1.0, 2.0]
    assert second[:, 0].tolist() == [1.0, 3.0]
