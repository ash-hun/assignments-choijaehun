"""Gold Set 초안을 만들 원문을 유형별로 고른다. seed가 같으면 같은 원문이 뽑힌다."""
import re
import random
import posixpath
from pathlib import Path
from pydantic import BaseModel

from app.schema.corpus_schema import CorpusManifest
from app.schema.gold_schema import GoldType

MIN_DOC_CHARS = 1500
SUMMARY_MIN_CHARS = 6000
TRAP_MIN_SIGNALS = 3
RELATIVE_LINK = re.compile(r"\]\((?!https?:|mailto:|#)([^)\s#]+)(?:#[^)\s]*)?\)")
# 버전 차이, 미리보기, 폐기 같은 표기가 많을수록 낡은 사전 지식으로 틀리기 쉬운 문서다.
TRAP_SIGNAL = re.compile(r"\bpreview\b|\bexperimental\b|\bdeprecated\b|\bv?\d+\.\d+\.\d+\b", re.IGNORECASE)
HEADING = re.compile(r"^(#{1,2})\s+(.+)$", re.MULTILINE)


class DraftTarget(BaseModel):
    """초안 하나를 만들 유형과 원문 문서 목록. unanswerable은 문서 없이 목차만 쓴다."""

    type: GoldType
    doc_ids: list[str]
    count: int = 1
    reasoning: bool = False


def load_documents(manifest: CorpusManifest, raw_dir: Path) -> dict[str, str]:
    """manifest 순서대로 문서 경로와 본문을 읽는다."""
    return {f.path: (raw_dir / f.path).read_text(encoding="utf-8") for f in manifest.files}


def internal_links(docs: dict[str, str]) -> dict[str, list[str]]:
    """문서마다 Corpus 안의 다른 문서를 가리키는 링크 대상을 모은다."""
    links: dict[str, list[str]] = {}
    for path, text in docs.items():
        targets = []
        for raw in RELATIVE_LINK.findall(text):
            target = posixpath.normpath(posixpath.join(posixpath.dirname(path), raw))
            if target.endswith("/"):
                target += "index.md"
            if target in docs and target != path and target not in targets:
                targets.append(target)
        links[path] = targets
    return links


def outline(docs: dict[str, str]) -> str:
    """문서별 H1, H2 제목만 모은 목차. 답 없는 문항을 만들 때 Corpus 범위를 알려주는 용도다."""
    lines = []
    for path, text in docs.items():
        headings = [h.strip() for _, h in HEADING.findall(text)]
        lines.append(f"- {path}: " + " | ".join(headings[:12]))
    return "\n".join(lines)


def plan_targets(
    docs: dict[str, str], plan: dict[GoldType, int], seed: int, prior_docs: set[str] | None = None, reasoning: int = 0,
) -> list[DraftTarget]:
    """유형별 개수만큼 원문을 고른다. 한 문서가 여러 문항에 몰리지 않게 이미 쓴 문서를 뒤로 미룬다.

    prior_docs는 다른 split에서 이미 근거로 쓴 문서로, 처음부터 쓴 것으로 친다. multi_doc 중 앞의 reasoning개는 추론 문항이다.
    """
    rng = random.Random(seed)
    eligible = sorted(p for p, t in docs.items() if len(t) >= MIN_DOC_CHARS)
    used: set[str] = set(prior_docs or ())
    targets: list[DraftTarget] = []

    def pick(pool: list[str], n: int) -> list[str]:
        shuffled = rng.sample(pool, len(pool))
        ordered = [p for p in shuffled if p not in used] + [p for p in shuffled if p in used]
        chosen = ordered[:n]
        used.update(chosen)
        return chosen

    for path in _stratified(eligible, plan.get("factual", 0), rng, used):
        targets.append(DraftTarget(type="factual", doc_ids=[path]))

    links = internal_links({p: docs[p] for p in eligible})
    pairs = [(a, b) for a in eligible for b in links[a]]
    rng.shuffle(pairs)
    chosen_pairs: list[tuple[str, str]] = []
    for a, b in sorted(pairs, key=lambda pair: (pair[0] in used) + (pair[1] in used)):
        if len(chosen_pairs) == plan.get("multi_doc", 0):
            break
        if all(a not in pair and b not in pair for pair in chosen_pairs):
            chosen_pairs.append((a, b))
            used.update((a, b))
    targets += [DraftTarget(type="multi_doc", doc_ids=[a, b], reasoning=n < reasoning) for n, (a, b) in enumerate(chosen_pairs)]

    long_docs = [p for p in eligible if len(docs[p]) >= SUMMARY_MIN_CHARS]
    targets += [DraftTarget(type="summary", doc_ids=[p]) for p in pick(long_docs, plan.get("summary", 0))]

    trap_docs = [p for p in eligible if len(TRAP_SIGNAL.findall(docs[p])) >= TRAP_MIN_SIGNALS]
    targets += [DraftTarget(type="trap", doc_ids=[p]) for p in pick(trap_docs, plan.get("trap", 0))]

    if plan.get("unanswerable", 0):
        targets.append(DraftTarget(type="unanswerable", doc_ids=[], count=plan["unanswerable"]))
    return targets


def _stratified(paths: list[str], n: int, rng: random.Random, used: set[str]) -> list[str]:
    """최상위 디렉토리(섹션)를 번갈아 돌며 n개를 고른다. 큰 섹션에 문항이 몰리지 않게 하기 위해서다."""
    by_section: dict[str, list[str]] = {}
    for p in paths:
        by_section.setdefault(p.split("/")[0] if "/" in p else "(root)", []).append(p)
    # 뒤에서 꺼내므로 이미 쓴 문서를 앞으로 보낸다. 쓴 문서가 없으면 순서가 그대로라 dev set 표집이 바뀌지 않는다.
    queues = {s: sorted(rng.sample(ps, len(ps)), key=lambda p: p not in used) for s, ps in sorted(by_section.items())}
    chosen: list[str] = []
    while len(chosen) < n and any(queues.values()):
        for section in sorted(queues):
            if queues[section] and len(chosen) < n:
                chosen.append(queues[section].pop())
    used.update(chosen)
    return chosen
