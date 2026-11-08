"""eval_run 기능의 LLM 응답 캐시(요청 해시, 다시 읽기, 중복 키 무시) 단위 테스트."""
from pathlib import Path

from app.client.llm_client import ChatMessage, LlmCompletion
from app.client.llm_cache import LlmCache


def test_cache_returns_the_stored_answer_after_reload(tmp_path: Path) -> None:
    path = tmp_path / "responses.jsonl"
    messages = [ChatMessage(role="user", content="q")]
    key = LlmCache.key("m", messages, 42, None, 100)
    completion = LlmCompletion(text="a [1]", model="m", input_tokens=10, output_tokens=2)

    LlmCache(path).put(key, completion, 123.4)
    LlmCache(path).put(key, completion, 999.0)

    assert LlmCache(path).get(key) == (completion, 123.4)
    assert len(path.read_text().splitlines()) == 1
    assert LlmCache(path).get(LlmCache.key("m", messages, 43, None, 100)) is None
