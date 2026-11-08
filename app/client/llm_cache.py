"""LLM 응답 캐시. 요청 내용 해시를 키로 JSONL에 쌓아, 같은 설정으로 다시 돌리면 API를 부르지 않고 같은 답을 낸다."""
import json
import hashlib
from pathlib import Path

from app.client.llm_client import ChatMessage, LlmCompletion


class LlmCache:
    """요청 내용 해시를 키로 응답을 JSONL에 쌓는다. 같은 설정으로 다시 돌리면 API를 부르지 않고 같은 답을 낸다."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._entries: dict[str, dict[str, object]] = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    entry = json.loads(line)
                    self._entries[entry["key"]] = entry

    @staticmethod
    def key(model: str, messages: list[ChatMessage], seed: int | None, temperature: float | None, max_tokens: int) -> str:
        """같은 요청이면 같은 키."""
        payload = {"model": model, "messages": [m.model_dump() for m in messages], "seed": seed,
                   "temperature": temperature, "max_tokens": max_tokens}
        return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

    def get(self, key: str) -> tuple[LlmCompletion, float] | None:
        """저장된 응답과 처음 호출했을 때의 지연(ms)."""
        entry = self._entries.get(key)
        if entry is None:
            return None
        return LlmCompletion.model_validate(entry["completion"]), float(str(entry["latency_ms"]))

    def put(self, key: str, completion: LlmCompletion, latency_ms: float) -> None:
        """응답 하나를 덧붙인다. 이미 있는 키는 다시 쓰지 않는다."""
        if key in self._entries:
            return
        entry: dict[str, object] = {"key": key, "completion": completion.model_dump(), "latency_ms": round(latency_ms, 1)}
        self._entries[key] = entry
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
