"""selection_run 기능의 데이터베이스 선정 보조 모듈(vector_projector, term_hasher) 단위 테스트."""
import numpy as np

from app.service.eval.vector_projector import project, exact_top_k
from app.service.eval.term_hasher import hash_terms


def test_project_is_deterministic_normalized_and_keeps_nearest_neighbors() -> None:
    rng = np.random.default_rng(0)
    base = rng.standard_normal((50, 32)).astype(np.float32)
    base /= np.linalg.norm(base, axis=1, keepdims=True)

    first = project(base, 256, seed=3)

    assert first.shape == (50, 256)
    assert np.allclose(first, project(base, 256, seed=3))
    assert np.allclose(np.linalg.norm(first, axis=1), 1.0, atol=1e-5)
    same_top1 = sum(exact_top_k(base, base[:10], 2)[i][1] == exact_top_k(first, first[:10], 2)[i][1] for i in range(10))
    assert same_top1 >= 7


def test_exact_top_k_orders_by_cosine() -> None:
    corpus = np.array([[1.0, 0.0], [0.0, 1.0], [0.7071, 0.7071]], dtype=np.float32)

    assert exact_top_k(corpus, np.array([[1.0, 0.0]], dtype=np.float32), 2) == [[0, 2]]


def test_hash_terms_counts_lowercased_tokens_deterministically() -> None:
    terms = hash_terms("UV sync uv")

    assert sorted(terms.values) == [1.0, 2.0]
    assert terms == hash_terms("uv SYNC uv")
