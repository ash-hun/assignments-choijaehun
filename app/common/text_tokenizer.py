"""BM25 sparse 검색용 단어 토큰화. Ingest(문서)와 Query(질의)가 같은 설정으로 써야 같은 단어가 같은 index로 간다."""
import re
from snowballstemmer import stemmer
from typing import Literal, Callable

# 영문 소문자와 숫자, 밑줄 묶음, 한글 묶음을 따로 잡아 "uv.lock이" 같은 조사 붙은 식별자를 "uv", "lock", "이"로 나눈다.
WORD = re.compile(r"[a-z0-9_]+|[가-힣]+")
# 점, 하이픈, 슬래시로 이어진 코드 식별자(uv.lock, --frozen, pyproject.toml)를 통째로 하나 더 남긴다.
IDENTIFIER = re.compile(r"-{1,2}[a-z0-9][a-z0-9_-]*|[a-z0-9_]+(?:[./-][a-z0-9_]+)+")
EDGE_PUNCTUATION = "`'\"()[]{}<>,.:;!?*#|"
# 형태소 분석기가 낸 토큰 중 글자나 숫자가 하나도 없는 것(구두점, 기호, 홀로 남은 자모)은 버린다.
MEANINGFUL = re.compile(r"[a-z0-9가-힣]")

SplitMode = Literal["whitespace", "word", "kiwi", "okt", "kkma"]
ANALYZERS = ("kiwi", "okt", "kkma")


class TextTokenizer:
    """소문자화한 뒤 split 방식으로 나눈다. word는 영어 어간 추출과 식별자 보존을 더할 수 있고, kiwi, okt, kkma는 형태소 분석기 출력을 그대로 쓴다."""

    def __init__(self, split: SplitMode, stem: bool = False, identifiers: bool = False) -> None:
        if split != "word" and (stem or identifiers):
            raise ValueError("stem and identifiers apply only to split='word'")
        self._split = split
        self._stemmer = stemmer("english") if stem else None
        self._identifiers = identifiers
        self._analyzer = _load_analyzer(split) if split in ANALYZERS else None

    @property
    def name(self) -> str:
        """인덱스 계약에 기록하는 설정 이름. 색인과 질의가 이 값으로 같은 토크나이저인지 대조한다."""
        return "+".join([self._split] + (["stem"] if self._stemmer else []) + (["ident"] if self._identifiers else []))

    def tokenize(self, text: str) -> list[str]:
        """텍스트를 토큰 목록으로 바꾼다. 순서와 중복을 유지해 단어 빈도를 셀 수 있게 한다."""
        lowered = text.lower()
        if self._split == "whitespace":
            return [t for t in (w.strip(EDGE_PUNCTUATION) for w in lowered.split()) if t]
        if self._analyzer is not None:
            return [t for t in (m.strip(EDGE_PUNCTUATION) for m in self._analyzer(lowered)) if MEANINGFUL.search(t)]
        words = WORD.findall(lowered)
        if self._stemmer is not None:
            words = [w if "가" <= w[0] <= "힣" else self._stemmer.stemWord(w) for w in words]
        if self._identifiers:
            words += IDENTIFIER.findall(lowered)
        return words


def _load_analyzer(name: str) -> Callable[[str], list[str]]:
    """형태소 분석기를 쓸 때만 import한다. 운영 이미지에는 korean 의존성 그룹과 JVM이 없다."""
    if name == "kiwi":
        from kiwipiepy import Kiwi
        kiwi = Kiwi()
        return lambda text: [token.form for token in kiwi.tokenize(text)]
    from konlpy.tag import Okt, Kkma
    tagger = Okt() if name == "okt" else Kkma()
    return lambda text: list(tagger.morphs(text))
