"""LLM 동시 호출 상한. 자리가 날 때까지 정해진 시간만 기다리고, 넘으면 LlmBusyError로 거절한다."""
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.common.upstream_error import LlmBusyError


class LlmGate:
    """업스트림 rate limit과 크레딧 소모가 몰리지 않게 한 프로세스의 동시 호출 수를 묶는다."""

    def __init__(self, limit: int, wait_seconds: float) -> None:
        self._semaphore = asyncio.Semaphore(limit)
        self._wait_seconds = wait_seconds

    @property
    def wait_seconds(self) -> float:
        """자리를 기다리는 최대 시간. 503 응답의 Retry-After 근거로도 쓴다."""
        return self._wait_seconds

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        """자리를 얻으면 들어가고, 블록이 끝나면 돌려준다."""
        try:
            await asyncio.wait_for(self._semaphore.acquire(), timeout=self._wait_seconds)
        except TimeoutError as error:
            raise LlmBusyError("llm concurrency limit reached") from error
        try:
            yield
        finally:
            self._semaphore.release()
