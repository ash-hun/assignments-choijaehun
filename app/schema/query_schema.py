"""질의응답 경로의 생성 결과 모델. 인용 번호는 프롬프트에 넣은 근거의 1부터 시작하는 순번이다."""
from pydantic import BaseModel


class ParsedAnswer(BaseModel):
    """존재하지 않는 인용 번호를 지운 답변, 본문에 나온 순서대로 중복 없이 모은 인용 번호, 지운 번호 수."""

    text: str
    citations: list[int]
    dropped: int
