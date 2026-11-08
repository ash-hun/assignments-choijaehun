"""gold_draft 기능의 원문 표집(gold_sampler) 단위 테스트."""
from app.service.eval.gold_sampler import outline, plan_targets, internal_links
from app.schema.gold_schema import GoldType

BODY = "x" * 2000


def make_docs() -> dict[str, str]:
    return {
        "index.md": "# Home\n" + BODY + " [a](concepts/a.md)",
        "concepts/a.md": "# A\n" + BODY + " [b](../guides/b.md#part) [ext](https://x.io)",
        "concepts/long.md": "# Long\n## Part\n" + "y" * 7000 + " preview experimental 1.2.3",
        "guides/b.md": "# B\n" + BODY + " [a](../concepts/a.md)",
        "guides/short.md": "# Short\ntiny",
    }


def test_internal_links_resolve_relative_paths_and_drop_external() -> None:
    links = internal_links(make_docs())

    assert links["concepts/a.md"] == ["guides/b.md"]
    assert links["index.md"] == ["concepts/a.md"]


def test_plan_targets_is_deterministic_and_respects_rules() -> None:
    docs = make_docs()
    plan: dict[GoldType, int] = {"factual": 2, "multi_doc": 1, "summary": 1, "trap": 1, "unanswerable": 3}

    first = plan_targets(docs, plan, seed=7)
    second = plan_targets(docs, plan, seed=7)

    assert first == second
    by_type = {t.type: t for t in first}
    assert "guides/short.md" not in {d for t in first for d in t.doc_ids}
    assert set(by_type["multi_doc"].doc_ids) in ({"concepts/a.md", "guides/b.md"}, {"index.md", "concepts/a.md"})
    assert by_type["summary"].doc_ids == ["concepts/long.md"]
    assert by_type["trap"].doc_ids == ["concepts/long.md"]
    assert by_type["unanswerable"].count == 3 and by_type["unanswerable"].doc_ids == []


def test_plan_targets_prefers_docs_outside_prior_and_marks_reasoning() -> None:
    docs = make_docs()
    plan: dict[GoldType, int] = {"factual": 2, "multi_doc": 1}

    targets = plan_targets(docs, plan, seed=7, prior_docs={"concepts/a.md"}, reasoning=1)

    factual = [t.doc_ids[0] for t in targets if t.type == "factual"]
    assert factual == ["index.md", "concepts/long.md"]
    assert [t.reasoning for t in targets if t.type == "multi_doc"] == [True]


def test_outline_lists_h1_and_h2_only() -> None:
    text = outline({"a.md": "# Title\n## Sub\n### Deep\nbody"})

    assert text == "- a.md: Title | Sub"
