"""gold_draft 기능의 번역 묶음 생성(GoldTranslator) 단위 테스트. LLM은 가짜 SDK로 대체한다."""
import json
import pytest
import asyncio
from typing import Any
from types import SimpleNamespace

from app.service.eval.gold_translator import GoldTranslator
from app.schema.gold_schema import GoldItem, GoldEvidence
from app.client.llm_client import LlmClient


class EchoCompletions:
    def __init__(self, drop: bool = False) -> None:
        self.drop = drop

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        prompt = kwargs["messages"][-1]["content"]
        rows = json.loads(prompt.split("<questions>")[1].split("</questions>")[0])
        out = [{"id": r["id"], "question": "번역: " + r["question"]} for r in rows]
        if self.drop:
            out = out[1:]
        return SimpleNamespace(
            model="fake",
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({"translations": out})))],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
        )


def make_items(n: int) -> list[GoldItem]:
    return [
        GoldItem(
            id=GoldItem.make_id("dev", "factual", i), split="dev", type="factual", question=f"q{i}", answerable=True,
            reference_answer="a", evidence=[GoldEvidence(doc_id="a.md", quote="x")], origin="llm_draft_reviewed",
        )
        for i in range(1, n + 1)
    ]


def make_translator(drop: bool = False) -> GoldTranslator:
    sdk: Any = SimpleNamespace(chat=SimpleNamespace(completions=EchoCompletions(drop)))
    return GoldTranslator(LlmClient(sdk, "fake"), seed=1, concurrency=2)


def test_translate_keeps_evidence_and_links_to_source_across_batches() -> None:
    items = make_items(10)

    translated = asyncio.run(make_translator().translate(items, "ko"))

    assert [t.translation_of for t in translated] == [i.id for i in items]
    assert translated[9].question == "번역: q10"
    assert translated[0].id == GoldItem.make_translation_id(items[0].id, "ko")
    assert all(t.evidence == i.evidence and t.language == "ko" for t, i in zip(translated, items))


def test_translate_fails_when_a_translation_is_missing() -> None:
    with pytest.raises(ValueError, match="missing translations"):
        asyncio.run(make_translator(drop=True).translate(make_items(3), "ko"))


def test_translated_item_requires_translation_of() -> None:
    with pytest.raises(ValueError, match="translation_of"):
        GoldItem.model_validate(make_items(1)[0].model_dump() | {"language": "ko"})
