"""Gold Set 초안 생성(gold-draft), 번역 묶음 생성(gold-translate), 검증(gold-check) 명령."""
import sys
import asyncio
import argparse
from pathlib import Path
from collections import Counter

from app.service.eval.gold_sampler import outline, plan_targets, load_documents
from app.schema.gold_schema import GoldItem, GoldType, GoldSplit, GoldLanguage
from app.service.eval.gold_drafter import PriorSet, GoldDrafter
from app.service.eval.retrieval_metric import shares_evidence
from app.service.eval.gold_translator import GoldTranslator
from app.service.eval.evidence_matcher import locate_quote
from app.common.settings import Settings, get_settings
from app.schema.corpus_schema import CorpusManifest
from app.cli.selection_cli import build_llm
from app.common.logger import get_logger

# dev set 구성은 project_planning/plan.md의 "dev set 구성", test set 구성은 research/gold_metric_selection.md를 따른다.
SPLIT_PLANS: dict[str, dict[GoldType, int]] = {
    "dev": {"factual": 12, "multi_doc": 8, "summary": 5, "trap": 5, "unanswerable": 8},
    "test": {"factual": 12, "multi_doc": 10, "summary": 6, "trap": 4, "unanswerable": 8},
}
# multi_doc 중 추론 문항 수.
REASONING_PLAN: dict[str, int] = {"dev": 0, "test": 4}
# split마다 표집 seed를 달리해 test가 dev와 같은 원문을 같은 순서로 뽑지 않게 한다. dev는 기존 값 그대로다.
SPLIT_SEED_OFFSET: dict[str, int] = {"dev": 0, "test": 1}
# test set이 근거를 겹치면 안 되는 split.
PRIOR_SPLIT: dict[str, GoldSplit] = {"test": "dev"}
DRAFT_DIR = "gold/drafts"
GOLD_DIR = "gold"

logger = get_logger(__name__)


def load_corpus(settings: Settings) -> dict[str, str]:
    """확정된 Corpus의 문서를 manifest 기준으로 읽는다."""
    manifest_path = settings.data_dir / "corpus" / "manifests" / f"{settings.corpus_name}.json"
    manifest = CorpusManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    return load_documents(manifest, settings.data_dir / "corpus" / "raw" / settings.corpus_name)


async def draft(settings: Settings, split: GoldSplit) -> Path:
    """초안을 만들어 drafts 디렉토리에 쓴다. 검수를 마친 Gold 파일은 건드리지 않는다."""
    docs = load_corpus(settings)
    prior = load_prior(settings, split)
    targets = plan_targets(
        docs, SPLIT_PLANS[split], settings.gold_seed + SPLIT_SEED_OFFSET[split], set(prior.quotes), REASONING_PLAN[split],
    )
    drafter = GoldDrafter(build_llm(settings), settings.llm_seed, settings.llm_concurrency)
    outcome = await drafter.draft(targets, docs, outline(docs), split, prior)
    out = settings.data_dir / DRAFT_DIR / f"{split}_draft.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(i.model_dump_json() + "\n" for i in outcome.items), encoding="utf-8")
    logger.info(
        "gold_draft_written", path=str(out), items=len(outcome.items), rejected=outcome.rejected,
        input_tokens=outcome.input_tokens, output_tokens=outcome.output_tokens,
    )
    return out


def load_prior(settings: Settings, split: GoldSplit) -> PriorSet:
    """이 split이 겹치면 안 되는 split의 근거 구절과 질문. 없으면 빈 값이다."""
    other = PRIOR_SPLIT.get(split)
    if other is None:
        return PriorSet()
    items, problems = read_gold(gold_path(settings, other, "en"))
    if problems:
        raise SystemExit(f"{other} gold file has problems: {problems}")
    quotes: dict[str, list[str]] = {}
    for item in items:
        for ev in item.evidence:
            quotes.setdefault(ev.doc_id, []).append(ev.quote)
    return PriorSet(quotes=quotes, questions=[i.question for i in items])


def gold_path(settings: Settings, split: GoldSplit, language: GoldLanguage) -> Path:
    """정본 경로. 영어 원문은 <split>_set.jsonl, 번역 묶음은 <split>_set_<언어>.jsonl."""
    suffix = "" if language == "en" else f"_{language}"
    return settings.data_dir / GOLD_DIR / f"{split}_set{suffix}.jsonl"


def read_gold(path: Path) -> tuple[list[GoldItem], list[str]]:
    """Gold 파일을 읽고 스키마를 통과하지 못한 줄을 문제로 모은다."""
    items: list[GoldItem] = []
    problems: list[str] = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            items.append(GoldItem.model_validate_json(line))
        except ValueError as e:
            problems.append(f"line {n}: {e}")
    return items, problems


async def translate(settings: Settings, split: GoldSplit, language: GoldLanguage) -> Path:
    """검수된 영어 정본을 옮겨 drafts 디렉토리에 쓴다. 번역 정본은 검수 후에 만든다."""
    items, problems = read_gold(gold_path(settings, split, "en"))
    if problems:
        raise SystemExit(f"source gold file has problems: {problems}")
    translator = GoldTranslator(build_llm(settings), settings.llm_seed, settings.llm_concurrency)
    translated = await translator.translate(items, language)
    out = settings.data_dir / DRAFT_DIR / f"{split}_{language}_draft.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(i.model_dump_json() + "\n" for i in translated), encoding="utf-8")
    logger.info("gold_translation_written", path=str(out), items=len(translated))
    return out


def check(settings: Settings, path: Path, source: Path | None = None) -> list[str]:
    """스키마, id 중복, 근거 인용의 원문 일치를 검사한다. 번역 행은 원문 행과 짝이 맞는지도 본다."""
    docs = load_corpus(settings)
    items, problems = read_gold(path)
    duplicated = [i for i, c in Counter(item.id for item in items).items() if c > 1]
    problems += [f"duplicate id: {i}" for i in duplicated]
    for item in items:
        for ev in item.evidence:
            if ev.doc_id not in docs or locate_quote(docs[ev.doc_id], ev.quote) != ev.quote:
                problems.append(f"{item.id}: evidence not verbatim in {ev.doc_id}")
    translated = [item for item in items if item.translation_of is not None]
    if translated and source is not None:
        originals = {item.id: item for item in read_gold(source)[0]}
        for item in translated:
            original = originals.get(item.translation_of) if item.translation_of else None
            if original is None:
                problems.append(f"{item.id}: translation_of {item.translation_of} not found in {source}")
            elif (original.type, original.evidence, original.reference_answer) != (item.type, item.evidence, item.reference_answer):
                problems.append(f"{item.id}: type, evidence or reference_answer differs from {original.id}")
        missing = set(originals) - {item.translation_of for item in translated}
        problems += [f"no translation for {i}" for i in sorted(map(str, missing))]
    split = items[0].split if items else None
    if split == "test":
        problems += [f"{item.id}: acceptance_criteria is empty" for item in items if not item.acceptance_criteria]
        prior = load_prior(settings, split)
        problems += [
            f"{item.id}: evidence shares a passage with the {PRIOR_SPLIT[split]} set in {ev.doc_id}"
            for item in items for ev in item.evidence
            if any(shares_evidence(ev.quote, q) for q in prior.quotes.get(ev.doc_id, []))
        ]
        sources = [item for item in items if item.translation_of is None]
        reasoning = sum(item.requires_reasoning for item in sources)
        if sources and reasoning < REASONING_PLAN[split]:
            problems.append(f"reasoning items {reasoning} < {REASONING_PLAN[split]}")
    counts = Counter(item.type for item in items)
    logger.info("gold_checked", path=str(path), items=len(items), by_type=dict(sorted(counts.items())), problems=len(problems))
    return problems


def main(argv: list[str] | None = None) -> int:
    """gold-draft: 초안 생성. gold-translate: 번역 묶음 초안. gold-check: 정본 검증, 문제가 있으면 종료 코드 1."""
    parser = argparse.ArgumentParser(prog="eval")
    parser.add_argument("command", choices=["gold-draft", "gold-translate", "gold-check"])
    parser.add_argument("--split", choices=sorted(SPLIT_PLANS), default="dev")
    parser.add_argument("--lang", choices=["en", "ko"], default="en", help="gold-translate 대상 언어, gold-check 대상 묶음")
    parser.add_argument("--file", type=Path, help="gold-check 대상 파일. 생략하면 split과 lang의 정본")
    args = parser.parse_args(argv)
    settings = get_settings()

    if args.command == "gold-draft":
        asyncio.run(draft(settings, args.split))
        return 0
    if args.command == "gold-translate":
        if args.lang == "en":
            raise SystemExit("gold-translate needs a target language other than en")
        asyncio.run(translate(settings, args.split, args.lang))
        return 0
    path = args.file or gold_path(settings, args.split, args.lang)
    source = gold_path(settings, args.split, "en") if args.lang != "en" else None
    problems = check(settings, path, source)
    for problem in problems:
        logger.error("gold_problem", detail=problem)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
