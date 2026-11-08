"""생성 답변의 [n] 인용 추출. 프롬프트에 없는 번호는 본문과 목록에서 지우고, 코드 안의 대괄호는 건드리지 않는다."""
import re

from app.schema.query_schema import ParsedAnswer

CITATION = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")
# 코드 블록과 인라인 코드 안의 a[0] 같은 표현은 인용이 아니다.
CODE = re.compile(r"```.*?```|`[^`\n]*`", re.DOTALL)


def parse_citations(text: str, evidence_count: int) -> ParsedAnswer:
    """[1], [1][3], [1, 3] 형식을 읽는다. 유효 번호는 1부터 evidence_count까지이고, 본문은 [1][3] 형식으로 맞춘다."""
    cited: list[int] = []
    dropped = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal dropped
        numbers = [int(n) for n in re.split(r"\s*,\s*", match.group(1))]
        valid = [n for n in numbers if 1 <= n <= evidence_count]
        dropped += len(numbers) - len(valid)
        cited.extend(n for n in valid if n not in cited)
        return "".join(f"[{n}]" for n in dict.fromkeys(valid))

    parts = []
    last = 0
    for code in CODE.finditer(text):
        parts.append(CITATION.sub(replace, text[last:code.start()]))
        parts.append(code.group())
        last = code.end()
    parts.append(CITATION.sub(replace, text[last:]))
    cleaned = re.sub(r"[ \t]+([.,;:!?])", r"\1", "".join(parts))
    return ParsedAnswer(text=cleaned.strip(), citations=cited, dropped=dropped)
