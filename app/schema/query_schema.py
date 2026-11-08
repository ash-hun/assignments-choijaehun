"""질의응답 경로의 요청, 응답, 생성 결과 모델. 인용 번호는 프롬프트에 넣은 근거의 1부터 시작하는 순번이다."""
from typing import Literal
from pydantic import BaseModel, Field

from app.schema.chunk_schema import Chunk

QueryStatus = Literal["answered", "insufficient_context"]


class ParsedAnswer(BaseModel):
    """존재하지 않는 인용 번호를 지운 답변, 본문에 나온 순서대로 중복 없이 모은 인용 번호, 지운 번호 수."""

    text: str
    citations: list[int]
    dropped: int


class RetrievedChunk(BaseModel):
    """검색된 청크 하나와 dense 코사인 유사도."""

    chunk: Chunk
    score: float


class QueryRequest(BaseModel):
    """질의 요청."""

    question: str = Field(min_length=1, max_length=1000, description="질문. 1자 이상 1000자 이하",
                          examples=["How do I change the uv cache directory?"])
    top_k: int | None = Field(default=None, ge=1, le=20, description="LLM에 넣을 근거 청크 수. 생략하면 서버 기본값(5)")


class Citation(BaseModel):
    """본문의 [ref] 인용이 가리키는 근거."""

    ref: int = Field(description="본문의 [n] 번호")
    doc_id: str = Field(description="문서 식별자(Corpus 기준 상대 경로)")
    title: str = Field(description="문서 제목")
    url: str = Field(description="색인한 판(고정 commit)의 원문 위치")
    chunk_id: str = Field(description="근거 청크 식별자")
    snippet: str = Field(description="근거 청크 앞부분")


class TokenUsage(BaseModel):
    """LLM 입력, 출력 토큰 수. LLM을 부르지 않았으면 0이다."""

    input_tokens: int = 0
    output_tokens: int = 0


class QueryMeta(BaseModel):
    """답변을 만든 구성과 처리 정보."""

    model: str
    embedding_model: str
    retrieval_scores: list[float]
    dropped_citations: int
    latency_ms: int
    usage: TokenUsage


class QueryResponse(BaseModel):
    """질의 응답. 근거가 부족하면 status가 insufficient_context이고 answer는 고정 안내 문구다."""

    status: QueryStatus
    answer: str
    citations: list[Citation]
    meta: QueryMeta
