"""실시간 평가의 변경 알림. 기록이나 판정이 늘 때마다 버전을 올려 대시보드 스트림이 새 집계를 보내게 한다."""
import asyncio


class LiveSignal:
    """프로세스 하나 안에서만 쓴다. 버전은 단조 증가해, 기다리는 쪽이 놓친 변경도 알아챈다."""

    def __init__(self) -> None:
        self._version = 0
        self._changed = asyncio.Condition()

    @property
    def version(self) -> int:
        """지금까지의 변경 횟수."""
        return self._version

    async def publish(self) -> None:
        """변경을 알린다."""
        async with self._changed:
            self._version += 1
            self._changed.notify_all()

    async def wait(self, seen: int, timeout: float) -> int:
        """seen보다 새 버전이 되거나 timeout이 지나면 현재 버전을 돌려준다."""
        async with self._changed:
            try:
                await asyncio.wait_for(self._changed.wait_for(lambda: self._version > seen), timeout)
            except TimeoutError:
                pass
            return self._version
