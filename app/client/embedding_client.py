"""로컬 임베딩 모델(fastembed, ONNX) 클라이언트. 모델 카드가 요구하는 질의, 문서 접두어를 호출자가 지정한다."""
import numpy as np
from pathlib import Path
from fastembed import TextEmbedding

from app.common.logger import get_logger

logger = get_logger(__name__)


class EmbeddingClient:
    """문서와 질의를 L2 정규화한 float32 벡터로 바꾼다. 모델 파일은 cache_dir에 받아 재사용한다."""

    def __init__(
        self, model_name: str, cache_dir: Path, query_prefix: str = "", document_prefix: str = "", batch_size: int = 32,
    ) -> None:
        self._model_name = model_name
        self._model = TextEmbedding(model_name=model_name, cache_dir=str(cache_dir))
        self._query_prefix = query_prefix
        self._document_prefix = document_prefix
        self._batch_size = batch_size

    @property
    def model_name(self) -> str:
        """임베딩 모델 이름."""
        return self._model_name

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        """문서 벡터. 행 순서는 입력 순서와 같다."""
        return self._embed([self._document_prefix + t for t in texts])

    def embed_queries(self, texts: list[str]) -> np.ndarray:
        """질의 벡터. fastembed의 query_embed 대신 접두어를 직접 붙여 모델마다 같은 규칙으로 다룬다."""
        return self._embed([self._query_prefix + t for t in texts])

    def token_count(self, text: str) -> int:
        """접두어를 붙인 문서 하나의 토큰 수. 모델 최대 입력을 넘는지 확인하는 데 쓴다."""
        return int(self._model.token_count(self._document_prefix + text))

    def _embed(self, texts: list[str]) -> np.ndarray:
        vectors = np.array(list(self._model.embed(texts, batch_size=self._batch_size)), dtype=np.float32)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        normalized: np.ndarray = vectors / np.where(norms == 0, 1, norms)
        return normalized
