"""데이터베이스 선정 실험의 sparse 기능 검사용 임시 인코더. 실제 BM25 토큰화는 토크나이저 선정 실험에서 정한다."""
import re
import zlib
from collections import Counter

from app.schema.vector_schema import SPARSE_DIM, SparseTerms

TOKEN = re.compile(r"[a-z0-9_.-]+")


def hash_terms(text: str) -> SparseTerms:
    """소문자 단어를 crc32로 해시해 단어 빈도를 값으로 둔다. 같은 입력이면 같은 벡터가 나온다."""
    counts = Counter(zlib.crc32(token.encode()) % SPARSE_DIM for token in TOKEN.findall(text.lower()))
    indices = sorted(counts)
    return SparseTerms(indices=indices, values=[float(counts[i]) for i in indices])
