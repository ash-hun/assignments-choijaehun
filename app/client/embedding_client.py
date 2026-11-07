"""로컬 임베딩 모델(fastembed, ONNX) 클라이언트. Embedding 선정 전까지 데이터베이스 선정 실험의 임시 벡터를 만든다."""
import numpy as np
from pathlib import Path
from fastembed import TextEmbedding

from app.common.logger import get_logger

logger = get_logger(__name__)


class EmbeddingClient:
    """문서와 질의를 L2 정규화한 float32 벡터로 바꾼다. 모델 파일은 cache_dir에 받아 재사용한다."""

    def __init__(self, model_name: str, cache_dir: Path, batch_size: int = 64) -> None:
        self._model_name = model_name
        self._model = TextEmbedding(model_name=model_name, cache_dir=str(cache_dir))
        self._batch_size = batch_size

    @property
    def model_name(self) -> str:
        """임베딩 모델 이름."""
        return self._model_name

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        """문서 벡터. 행 순서는 입력 순서와 같다."""
        return _normalize(np.array(list(self._model.embed(texts, batch_size=self._batch_size)), dtype=np.float32))

    def embed_queries(self, texts: list[str]) -> np.ndarray:
        """질의 벡터. 모델이 질의용 접두어를 요구하면 fastembed가 붙인다."""
        return _normalize(np.array(list(self._model.query_embed(texts)), dtype=np.float32))


def _normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.where(norms == 0, 1, norms)
