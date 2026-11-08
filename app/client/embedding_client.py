"""로컬 임베딩 모델(fastembed, ONNX) 클라이언트. 모델 카드가 요구하는 질의, 문서 접두어를 호출자가 지정한다."""
import numpy as np
from pathlib import Path
from tokenizers import Tokenizer
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
        self._counter: Tokenizer | None = None

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
        """접두어를 붙인 문서 하나의 잘리기 전 토큰 수(특수 토큰 포함). 모델 최대 입력을 넘는지 확인하는 데 쓴다.

        fastembed의 token_count는 최대 입력에서 잘린 뒤의 수를 돌려줘 넘침을 볼 수 없어서, 잘림을 끈 사본으로 센다.
        """
        return len(self._tokenizer().encode(self._document_prefix + text).ids)

    def token_offsets(self, text: str) -> list[tuple[int, int]]:
        """접두어 없이 토큰화한 각 토큰의 문자 위치(시작, 끝). 특수 토큰은 뺀다. 긴 문서를 한 번만 토큰화해 구간 길이를 셀 때 쓴다."""
        encoding = self._tokenizer().encode(text, add_special_tokens=False)
        return list(encoding.offsets)

    def _tokenizer(self) -> Tokenizer:
        if self._counter is None:
            # ponytail: fastembed 내부 속성(model.tokenizer)에 기댄다. fastembed를 0.10 이상으로 올리면 확인.
            self._model.token_count("")
            source = getattr(self._model.model, "tokenizer")
            self._counter = Tokenizer.from_str(source.to_str())
            self._counter.no_truncation()
            self._counter.no_padding()
        return self._counter

    def _embed(self, texts: list[str]) -> np.ndarray:
        vectors = np.array(list(self._model.embed(texts, batch_size=self._batch_size)), dtype=np.float32)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        normalized: np.ndarray = vectors / np.where(norms == 0, 1, norms)
        return normalized
