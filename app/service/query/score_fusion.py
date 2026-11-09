"""dense와 BM25 검색 결과를 한 순위로 합치는 융합식. 같은 입력이면 같은 순위가 나오도록 동점은 chunk_id 순으로 정한다."""

Scored = list[tuple[str, float]]


def min_max(scored: Scored) -> dict[str, float]:
    """목록 안에서 0~1로 정규화한다. 점수가 모두 같으면 모두 1이다(목록에 들었다는 사실만 남긴다)."""
    if not scored:
        return {}
    low = min(s for _, s in scored)
    high = max(s for _, s in scored)
    if high == low:
        return {chunk_id: 1.0 for chunk_id, _ in scored}
    return {chunk_id: (s - low) / (high - low) for chunk_id, s in scored}


def convex_combination(dense: Scored, sparse: Scored, alpha: float) -> Scored:
    """alpha·minmax(dense) + (1−alpha)·minmax(sparse). 한쪽 목록에만 있는 후보는 다른 쪽 점수를 0으로 둔다."""
    if not 0.0 <= alpha <= 1.0:
        raise ValueError(f"alpha must be in [0, 1], got {alpha}")
    dense_norm, sparse_norm = min_max(dense), min_max(sparse)
    fused = {cid: alpha * dense_norm.get(cid, 0.0) + (1 - alpha) * sparse_norm.get(cid, 0.0)
             for cid in dense_norm.keys() | sparse_norm.keys()}
    return ordered(fused)


def reciprocal_rank_fusion(dense: list[str], sparse: list[str], k: int) -> Scored:
    """Σ 1/(k + rank), rank는 1부터. 점수 크기는 쓰지 않는다."""
    if k < 0:
        raise ValueError(f"k must be non-negative, got {k}")
    fused: dict[str, float] = {}
    for ranking in (dense, sparse):
        for rank, chunk_id in enumerate(ranking, start=1):
            fused[chunk_id] = fused.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return ordered(fused)


def ordered(scores: dict[str, float]) -> Scored:
    """점수 내림차순, 동점은 chunk_id 오름차순."""
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))
