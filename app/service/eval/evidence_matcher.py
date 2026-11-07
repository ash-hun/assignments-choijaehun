"""근거 인용이 원문이나 청크에 들어 있는지 판정한다. 공백 차이만 허용하고 나머지는 글자 그대로 비교한다."""
import re

WHITESPACE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """연속 공백과 줄바꿈을 공백 하나로 바꾼다."""
    return WHITESPACE.sub(" ", text).strip()


def locate_quote(source: str, quote: str) -> str | None:
    """source 안에서 quote와 공백만 다른 원문 구간을 찾아 원문 그대로 돌려준다. 없으면 None."""
    target = normalize(quote)
    if not target:
        return None
    if quote in source:
        return quote
    pattern = r"\s+".join(re.escape(token) for token in target.split(" "))
    matched = re.search(pattern, source)
    return matched.group(0) if matched else None


def contains_quote(text: str, quote: str) -> bool:
    """text가 quote를 공백 차이 없이 포함하는지."""
    return normalize(quote) in normalize(text)
