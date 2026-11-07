"""데이터셋 선정 실험에서 Corpus 후보의 규모, 구조, 파싱 난이도, 함정 요소를 수치로 잰다."""
import re
import statistics
from pathlib import Path

from app.schema.corpus_schema import CorpusProfile, CorpusManifest

# 페이지 환산 규칙. 과제의 "50페이지" 기준을 비교하려는 관례값이며 언어별 A4 한 쪽 분량에 맞췄다.
CHARS_PER_PAGE = {"ko": 1500, "en": 3000}
STUB_CHARS = 300
FENCE = re.compile(r"^\s*(```|~~~)")
HEADING = re.compile(r"^(#{1,6})\s+\S")
TABLE_LINE = re.compile(r"^\s*\|")
FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
MARKUP_NOISE = re.compile(r"\{\{[<%].*?[%>]\}\}|<[A-Za-z][^>]*>|^\s*(?:!!!|\?\?\?|:::)", re.MULTILINE)
VERSION = re.compile(r"\bv?\d+\.\d+(?:\.\d+)?\b")
# 외부 URL, 메일, 같은 문서 안 앵커를 뺀 링크를 문서 사이 연결로 본다.
INTERNAL_LINK = re.compile(r"\]\((?!https?:|mailto:|#)[^)\s]+\)")
FRONT_MATTER_TITLE = re.compile(r"\A---\n.*?^title:\s*(.+?)\s*$", re.DOTALL | re.MULTILINE)
HEADING_ANCHOR = re.compile(r"\s*\{\s*#[^}]*\}\s*$")


def profile_corpus(manifest: CorpusManifest, raw_dir: Path) -> CorpusProfile:
    """manifest의 모든 파일을 읽어 후보 비교용 통계를 만든다."""
    source = manifest.source
    doc_chars: list[int] = []
    heading_depths: dict[int, int] = {}
    code_chars = table_lines = total_lines = noise = versions = links = linked_docs = 0
    titles: list[str] = []

    for entry in manifest.files:
        original = (raw_dir / entry.path).read_text(encoding="utf-8")
        text = FRONT_MATTER.sub("", original)
        titles.append(_title(original, text))
        doc_chars.append(len(text))
        in_code = False
        prose: list[str] = []
        for line in text.splitlines():
            total_lines += 1
            if FENCE.match(line):
                in_code = not in_code
                continue
            if in_code:
                code_chars += len(line)
                continue
            prose.append(line)
            heading = HEADING.match(line)
            if heading:
                depth = len(heading.group(1))
                heading_depths[depth] = heading_depths.get(depth, 0) + 1
            if TABLE_LINE.match(line):
                table_lines += 1
        prose_text = "\n".join(prose)
        noise += len(MARKUP_NOISE.findall(prose_text))
        versions += len(VERSION.findall(prose_text))
        doc_links = len(INTERNAL_LINK.findall(prose_text))
        links += doc_links
        linked_docs += 1 if doc_links else 0

    documents = len(doc_chars)
    total_chars = sum(doc_chars)
    return CorpusProfile(
        name=source.name,
        language=source.language,
        license=source.license,
        commit=source.commit,
        documents=documents,
        total_chars=total_chars,
        estimated_pages=round(total_chars / CHARS_PER_PAGE[source.language], 1),
        median_doc_chars=int(statistics.median(doc_chars)) if doc_chars else 0,
        stub_documents=sum(1 for c in doc_chars if c < STUB_CHARS),
        heading_depth_counts=dict(sorted(heading_depths.items())),
        max_heading_depth=max(heading_depths, default=0),
        code_char_ratio=round(code_chars / total_chars, 3) if total_chars else 0.0,
        table_line_ratio=round(table_lines / total_lines, 3) if total_lines else 0.0,
        markup_noise_per_doc=round(noise / documents, 2) if documents else 0.0,
        version_mentions_per_doc=round(versions / documents, 2) if documents else 0.0,
        internal_links_per_doc=round(links / documents, 2) if documents else 0.0,
        linked_doc_ratio=round(linked_docs / documents, 3) if documents else 0.0,
        duplicate_title_ratio=round(_duplicate_ratio(titles), 3),
    )


def _title(original: str, body: str) -> str:
    """front matter의 title, 없으면 첫 H1. 제목 뒤 앵커 표기는 뗀다."""
    matched = FRONT_MATTER_TITLE.match(original)
    if matched:
        return matched.group(1).strip("'\" ")
    for line in body.splitlines():
        if line.startswith("# "):
            return HEADING_ANCHOR.sub("", line[2:]).strip()
    return ""


def _duplicate_ratio(titles: list[str]) -> float:
    """다른 문서와 제목이 같은 문서의 비율. 제목이 없는 문서는 세지 않는다."""
    named = [t for t in titles if t]
    if not named:
        return 0.0
    counts: dict[str, int] = {}
    for t in named:
        counts[t] = counts.get(t, 0) + 1
    return sum(1 for t in named if counts[t] > 1) / len(named)
