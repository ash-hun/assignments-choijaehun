"""Markdown 원문에서 검색에 쓸모없는 표기만 지운다. Markdown 링크와 코드, 자리표시자(<name>)는 남긴다."""
import re

FRONT_MATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
# CLI 사용법의 <name>, <version> 같은 자리표시자와 구분하려고 실제 HTML 태그 이름만 지운다.
HTML_TAG = re.compile(r"</?(?:p|img|i|b|a|div|span|br|details|summary|sup|sub|picture|source)\b[^>]*>", re.IGNORECASE)
BLANK_LINES = re.compile(r"\n{3,}")
TITLE_FIELD = re.compile(r"^title:\s*(.+?)\s*$", re.MULTILINE)
FIRST_H1 = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


def clean_text(text: str) -> str:
    """front matter, HTML 주석, HTML 태그를 지우고 연속 빈 줄을 하나로 줄인다. 근거 인용에도 같은 함수를 쓴다."""
    text = FRONT_MATTER.sub("", text)
    text = HTML_COMMENT.sub("", text)
    text = HTML_TAG.sub("", text)
    return BLANK_LINES.sub("\n\n", text).strip()


def extract_title(raw: str, doc_id: str) -> str:
    """front matter의 title, 없으면 첫 H1, 둘 다 없으면 doc_id."""
    front = FRONT_MATTER.match(raw)
    if front:
        field = TITLE_FIELD.search(front.group(0))
        if field:
            return field.group(1).strip("'\" ")
    heading = FIRST_H1.search(FRONT_MATTER.sub("", raw))
    return heading.group(1) if heading else doc_id
