"""query 기능의 LLM 동시 호출 상한(자리 대기, 대기 한도 초과 거절, 자리 반환) 단위 테스트."""
import pytest
import asyncio

from app.common.upstream_error import LlmBusyError
from app.service.query.llm_gate import LlmGate


def test_second_caller_is_rejected_when_the_only_slot_stays_busy() -> None:
    async def scenario() -> None:
        gate = LlmGate(1, 0.01)
        async with gate.slot():
            with pytest.raises(LlmBusyError):
                async with gate.slot():
                    pass

    asyncio.run(scenario())


def test_slot_is_returned_after_the_block_even_on_error() -> None:
    async def scenario() -> None:
        gate = LlmGate(1, 0.01)
        with pytest.raises(ValueError):
            async with gate.slot():
                raise ValueError("boom")
        async with gate.slot():
            pass

    asyncio.run(scenario())
