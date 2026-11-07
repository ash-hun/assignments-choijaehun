"""실제 임베딩을 무작위 가우시안 투영으로 다른 차원에 옮긴다. 이웃 관계를 대체로 보존해 DB 실험에서 차원만 바꿔 볼 수 있다."""
import numpy as np


def project(vectors: np.ndarray, dim: int, seed: int) -> np.ndarray:
    """(n, d) 벡터를 (n, dim)으로 옮기고 L2 정규화한다. 같은 seed면 같은 투영 행렬을 쓴다."""
    if dim == vectors.shape[1]:
        same: np.ndarray = vectors.astype(np.float32)
        return same
    rng = np.random.default_rng(seed)
    matrix = rng.standard_normal((vectors.shape[1], dim)).astype(np.float32) / np.sqrt(dim)
    projected = vectors @ matrix
    norms = np.linalg.norm(projected, axis=1, keepdims=True)
    normalized: np.ndarray = (projected / np.where(norms == 0, 1, norms)).astype(np.float32)
    return normalized


def exact_top_k(corpus: np.ndarray, queries: np.ndarray, k: int) -> list[list[int]]:
    """정규화된 벡터의 코사인 유사도 전수 비교. ANN 재현율의 기준값이다."""
    scores = queries @ corpus.T
    order = np.argsort(-scores, axis=1, kind="stable")[:, :k]
    return [row.tolist() for row in order]
