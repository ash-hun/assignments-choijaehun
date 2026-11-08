"""엘리스 ML API(OpenAI 호환) 채팅 호출 클라이언트. 타임아웃과 재시도는 SDK 설정으로 건다."""
from typing import Any, cast
from pydantic import BaseModel
from openai import AsyncOpenAI, omit
from openai.types.chat import ChatCompletionMessageParam
from openai.types.shared_params import ResponseFormatJSONSchema

from app.common.logger import get_logger

logger = get_logger(__name__)


class ChatMessage(BaseModel):
    """채팅 메시지 하나."""

    role: str
    content: str


class LlmCompletion(BaseModel):
    """생성 결과와 비용 계산용 토큰 수."""

    text: str
    model: str
    input_tokens: int
    output_tokens: int


class LlmClient:
    """모델 하나에 고정된 채팅 클라이언트. SDK 인스턴스는 생성자로 주입한다."""

    def __init__(self, sdk: AsyncOpenAI, model: str) -> None:
        self._sdk = sdk
        self._model = model

    @property
    def model(self) -> str:
        """호출 대상 모델명."""
        return self._model

    async def complete(
        self,
        messages: list[ChatMessage],
        seed: int | None,
        max_completion_tokens: int,
        temperature: float | None = None,
        json_schema: dict[str, Any] | None = None,
    ) -> LlmCompletion:
        """비스트리밍 채팅 호출. seed나 temperature가 None이면 보내지 않는다(모델마다 거부하는 인자가 다르다). json_schema가 있으면 구조화 출력을 강제한다."""
        response_format = (
            {"type": "json_schema", "json_schema": {"name": "output", "schema": json_schema, "strict": True}}
            if json_schema
            else None
        )
        response = await self._sdk.chat.completions.create(
            model=self._model,
            messages=cast(list[ChatCompletionMessageParam], [m.model_dump() for m in messages]),
            seed=omit if seed is None else seed,
            max_completion_tokens=max_completion_tokens,
            temperature=omit if temperature is None else temperature,
            response_format=omit if response_format is None else cast(ResponseFormatJSONSchema, response_format),
        )
        usage = response.usage
        return LlmCompletion(
            text=response.choices[0].message.content or "",
            model=response.model or self._model,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )
