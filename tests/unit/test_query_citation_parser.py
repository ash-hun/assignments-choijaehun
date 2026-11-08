"""query 기능의 인용 추출(유효 번호, 형식 통일, 코드 안 대괄호 보존) 단위 테스트."""
from app.service.query.citation_parser import parse_citations


def test_valid_citations_are_collected_in_order_and_normalized() -> None:
    parsed = parse_citations("Use uv sync [2]. It reads uv.lock [1, 2][3].", 3)

    assert (parsed.citations, parsed.dropped) == ([2, 1, 3], 0)
    assert parsed.text == "Use uv sync [2]. It reads uv.lock [1][2][3]."


def test_unknown_numbers_are_removed_and_code_brackets_are_kept() -> None:
    parsed = parse_citations("Index with `args[0]` [9].\n```\nx = a[1]\n```\nDone [1].", 2)

    assert (parsed.citations, parsed.dropped) == ([1], 1)
    assert parsed.text == "Index with `args[0]`.\n```\nx = a[1]\n```\nDone [1]."
