"""selection_run 기능의 closed-book 검증(ClosedBookProber) 단위 테스트. LLM 호출은 가짜 SDK로 대체한다."""
import asyncio
from typing import Any
from openai import omit
from types import SimpleNamespace

from app.service.eval.closed_book_prober import ClosedBookProber, SYSTEM_PROMPT
from app.schema.selection_schema import ClosedBookQuestion
from app.client.llm_client import LlmClient


class FakeCompletions:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        question = kwargs["messages"][-1]["content"]
        return SimpleNamespace(
            model="fake-model",
            choices=[SimpleNamespace(message=SimpleNamespace(content=f"answer to {question}"))],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
        )


def make_question(qid: str) -> ClosedBookQuestion:
    return ClosedBookQuestion(
        id=qid, category="conceptual", question=f"q{qid}", reference_answer="r", source_path="a.md", evidence="e",
    )


def test_probe_repeats_each_question_per_seed_in_order() -> None:
    completions = FakeCompletions()
    sdk: Any = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    prober = ClosedBookProber(LlmClient(sdk, "fake-model"), seeds=[7, 8], concurrency=2)

    answers = asyncio.run(prober.probe("sample", [make_question("1"), make_question("2")]))

    assert [(a.id, a.seed) for a in answers] == [("1", 7), ("1", 8), ("2", 7), ("2", 8)]
    assert answers[2].answer == "answer to q2"
    assert all(c["temperature"] is omit and "max_tokens" not in c for c in completions.calls)
    assert completions.calls[0]["messages"][0]["content"] == SYSTEM_PROMPT
    assert answers[0].grade is None


def test_probe_sends_temperature_only_when_configured() -> None:
    completions = FakeCompletions()
    sdk: Any = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    prober = ClosedBookProber(LlmClient(sdk, "m"), seeds=[1], concurrency=1, temperature=0.0)

    asyncio.run(prober.probe("sample", [make_question("1")]))

    assert completions.calls[0]["temperature"] == 0.0


def test_probe_of_no_questions_makes_no_calls() -> None:
    completions = FakeCompletions()
    sdk: Any = SimpleNamespace(chat=SimpleNamespace(completions=completions))

    answers = asyncio.run(ClosedBookProber(LlmClient(sdk, "m"), seeds=[1], concurrency=1).probe("sample", []))

    assert answers == []
    assert completions.calls == []
