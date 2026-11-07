"""벡터 DB 저장소가 주고받는 sparse 벡터와 인덱스 계약 모델."""
from pydantic import BaseModel, Field, model_validator

# sparse 벡터 index 공간 크기. pgvector sparsevec 차원 상한(10억) 안에서 해시 충돌이 적은 크기다.
SPARSE_DIM = 1 << 20


class SparseTerms(BaseModel):
    """클라이언트에서 토큰화해 만든 sparse 벡터. indices는 오름차순이고 중복이 없다."""

    indices: list[int]
    values: list[float]

    @model_validator(mode="after")
    def _aligned(self) -> "SparseTerms":
        if len(self.indices) != len(self.values) or self.indices != sorted(set(self.indices)):
            raise ValueError("indices must be sorted, unique and aligned with values")
        return self


class IndexContract(BaseModel):
    """색인과 질의가 반드시 같아야 하는 설정. Ingest가 컬렉션에 기록하고 Query가 기동 시 대조한다."""

    embedding_model: str = Field(min_length=1)
    tokenizer: str = Field(min_length=1)
    chunk_config_hash: str = Field(min_length=1)
