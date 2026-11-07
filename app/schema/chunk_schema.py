"""Ingest 경로의 문서와 청크 모델. 청크 id는 내용에서 계산해 재실행해도 같은 값이 나온다."""
from pydantic import BaseModel, Field

from app.common.content_hasher import sha256_text


class Document(BaseModel):
    """정제를 마친 원문 문서 하나. doc_id는 Corpus 기준 상대 경로다."""

    doc_id: str
    title: str
    text: str


class Chunk(BaseModel):
    """검색 단위. chunk_id는 (doc_id, text)의 sha256 앞 32자다."""

    chunk_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    doc_id: str
    ordinal: int = Field(ge=0)
    text: str = Field(min_length=1)

    @staticmethod
    def make_id(doc_id: str, text: str) -> str:
        """같은 문서의 같은 내용이면 같은 id. 순번은 넣지 않아 앞 청크가 바뀌어도 뒤 청크 id가 유지된다."""
        return sha256_text(f"{doc_id}\n{text}")[:32]
