"""gold_draft 기능의 초안 생성(GoldDrafter)과 근거 대조(evidence_matcher) 단위 테스트. LLM은 가짜 SDK로 대체한다."""
import json
import asyncio
from typing import Any
from types import SimpleNamespace

from app.service.eval.evidence_matcher import locate_quote, contains_quote
from app.service.eval.gold_drafter import PriorSet, GoldDrafter
from app.service.eval.gold_sampler import DraftTarget
from app.client.llm_client import LlmClient
from app.schema.gold_schema import GoldItem

DOCS = {"a.md": "Use `uv sync`\nto install.\nThe default is 5 minutes.", "b.md": "Locks are universal."}
CRITERIA = {"acceptance_criteria": ["says 5 minutes"], "rejection_criteria": []}


class ScriptedCompletions:
    def __init__(self, replies: list[dict[str, Any]]) -> None:
        self.replies = replies
        self.prompts: list[str] = []

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        self.prompts.append(kwargs["messages"][-1]["content"])
        reply = self.replies.pop(0)
        return SimpleNamespace(
            model="fake",
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(reply)))],
            usage=SimpleNamespace(prompt_tokens=3, completion_tokens=2),
        )


def make_drafter(replies: list[dict[str, Any]]) -> tuple[GoldDrafter, ScriptedCompletions]:
    completions = ScriptedCompletions(replies)
    sdk: Any = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return GoldDrafter(LlmClient(sdk, "fake"), seed=1, concurrency=2), completions


def test_locate_quote_tolerates_whitespace_only() -> None:
    assert locate_quote(DOCS["a.md"], "Use `uv sync` to install.") == "Use `uv sync`\nto install."
    assert locate_quote(DOCS["a.md"], "Use uv sync to install.") is None
    assert contains_quote("chunk: Use `uv sync`  to install. more", "Use `uv sync`\nto install.")


def test_draft_keeps_verbatim_evidence_and_numbers_ids() -> None:
    reply = {"question": "q?", "reference_answer": "5", "evidence": [{"doc_id": "a.md", "quote": "The default is 5 minutes."}], **CRITERIA}
    drafter, _ = make_drafter([reply])

    outcome = asyncio.run(drafter.draft([DraftTarget(type="factual", doc_ids=["a.md"])], DOCS, "", "dev"))

    assert [i.id for i in outcome.items] == [GoldItem.make_id("dev", "factual", 1)]
    assert outcome.items[0].evidence[0].quote == "The default is 5 minutes."
    assert outcome.items[0].acceptance_criteria == ["says 5 minutes"]
    assert outcome.rejected == 0


def test_draft_retries_with_feedback_then_rejects_unverifiable_evidence() -> None:
    bad = {"question": "q?", "reference_answer": "a", "evidence": [{"doc_id": "a.md", "quote": "not in the text"}], **CRITERIA}
    drafter, completions = make_drafter([bad, bad])

    outcome = asyncio.run(drafter.draft([DraftTarget(type="factual", doc_ids=["a.md"])], DOCS, "", "dev"))

    assert outcome.items == []
    assert outcome.rejected == 1
    assert "not found verbatim" in completions.prompts[1]


def test_multi_doc_draft_requires_evidence_from_every_document() -> None:
    one_doc = {"question": "q?", "reference_answer": "a", "evidence": [{"doc_id": "a.md", "quote": "Use `uv sync`"}], **CRITERIA}
    both = {"question": "q?", "reference_answer": "a", "evidence": [
        {"doc_id": "a.md", "quote": "Use `uv sync`"}, {"doc_id": "b.md", "quote": "Locks are universal."}], **CRITERIA}
    drafter, _ = make_drafter([one_doc, both])

    outcome = asyncio.run(drafter.draft([DraftTarget(type="multi_doc", doc_ids=["a.md", "b.md"])], DOCS, "", "dev"))

    assert outcome.items[0].gold_doc_ids == ["a.md", "b.md"]


def test_unanswerable_draft_has_no_evidence_and_keeps_reason() -> None:
    reply = {"items": [{"question": "roadmap?", "why_unanswerable": "not documented", "rejection_criteria": ["invents a date"]}]}
    drafter, _ = make_drafter([reply])

    outcome = asyncio.run(drafter.draft([DraftTarget(type="unanswerable", doc_ids=[], count=1)], DOCS, "- a.md: A", "dev"))

    item = outcome.items[0]
    assert (item.id, item.answerable, item.evidence, item.notes) == (GoldItem.make_id("dev", "unanswerable", 1), False, [], "not documented")
    assert item.acceptance_criteria and item.rejection_criteria == ["invents a date"]


def test_draft_rejects_evidence_reused_from_prior_set_and_tells_the_model() -> None:
    reused = {"question": "q?", "reference_answer": "5", "evidence": [{"doc_id": "a.md", "quote": "The default is 5 minutes."}], **CRITERIA}
    fresh = {"question": "q?", "reference_answer": "sync", "evidence": [{"doc_id": "a.md", "quote": "Use `uv sync`"}], **CRITERIA}
    drafter, completions = make_drafter([reused, fresh])
    prior = PriorSet(quotes={"a.md": ["The default is 5 minutes."]})

    outcome = asyncio.run(drafter.draft([DraftTarget(type="factual", doc_ids=["a.md"])], DOCS, "", "test", prior))

    assert outcome.items[0].evidence[0].quote == "Use `uv sync`"
    assert "already used" in completions.prompts[0]
    assert "reuse passages" in completions.prompts[1]


def test_reasoning_target_uses_reasoning_instruction_and_marks_item() -> None:
    both = {"question": "q?", "reference_answer": "a", "evidence": [
        {"doc_id": "a.md", "quote": "Use `uv sync`"}, {"doc_id": "b.md", "quote": "Locks are universal."}], **CRITERIA}
    drafter, completions = make_drafter([both])
    target = DraftTarget(type="multi_doc", doc_ids=["a.md", "b.md"], reasoning=True)

    outcome = asyncio.run(drafter.draft([target], DOCS, "", "test"))

    assert outcome.items[0].requires_reasoning is True
    assert "combine a condition" in completions.prompts[0]
