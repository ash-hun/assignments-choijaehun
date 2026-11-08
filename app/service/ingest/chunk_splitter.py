"""문서를 청크로 나눈다. 앞선 선정 실험이 쓴 문자 수 고정 분할과, Chunking 선정 실험이 비교하는 토큰 기준 분할 다섯 방식이 있다."""
import re
import bisect
import numpy as np
from typing import Literal, Callable

from app.schema.chunk_schema import Chunk, Document

ChunkMethod = Literal["fixed", "sliding", "recursive", "structure", "semantic"]
TokenCounter = Callable[[str], int]
Embedder = Callable[[list[str]], np.ndarray]
TokenOffsets = Callable[[str], list[tuple[int, int]]]
Span = tuple[int, int]

# 고정 길이는 단어 경계만 본다. 재귀 분할은 문단, 줄, 문장, 단어 순으로 큰 경계부터 시도한다.
WORD_BOUNDARIES = (re.compile(r"\s+"),)
PARAGRAPH_BOUNDARIES = (re.compile(r"\n\s*\n"), re.compile(r"\n"), re.compile(r"(?<=[.!?])\s+"), re.compile(r"\s+"))
HEADING = re.compile(r"^#{1,6}\s")
# 시맨틱 분할의 문장 단위. 문단 경계와 문장 끝에서 자른다.
SENTENCE = re.compile(r"\n\s*\n|(?<=[.!?])\s+")
# 이웃 문장 거리가 문서 안 상위 5%에 드는 곳에서 자른다(LangChain SemanticChunker 기본값).
SEMANTIC_PERCENTILE = 95.0
FENCE = re.compile(r"^\s*(```|~~~)")


class FixedLengthSplitter:
    """max_chars 이하가 되도록 공백 경계에서 자른다. 공백이 없는 긴 토큰은 max_chars에서 강제로 자른다."""

    def __init__(self, max_chars: int, overlap_chars: int = 0) -> None:
        if max_chars <= 0 or not 0 <= overlap_chars < max_chars:
            raise ValueError("need max_chars > 0 and 0 <= overlap_chars < max_chars")
        self._max = max_chars
        self._overlap = overlap_chars

    def split(self, document: Document) -> list[Chunk]:
        """문서 하나를 순서대로 자른다. 같은 입력이면 같은 청크와 id가 나온다."""
        text = document.text
        chunks: list[Chunk] = []
        start = 0
        while start < len(text):
            end = min(start + self._max, len(text))
            if end < len(text):
                boundary = text.rfind(" ", start + 1, end)
                newline = text.rfind("\n", start + 1, end)
                cut = max(boundary, newline)
                end = cut if cut > start else end
            piece = text[start:end].strip()
            if piece:
                chunks.append(Chunk(chunk_id=Chunk.make_id(document.doc_id, piece), doc_id=document.doc_id, ordinal=len(chunks), text=piece))
            if end >= len(text):
                break
            start = max(end - self._overlap, start + 1)
            # 경계의 공백이 다음 청크의 길이 예산을 차지하지 않게 건너뛴다.
            while start < len(text) and text[start].isspace():
                start += 1
        return chunks


class ChunkSplitter:
    """임베딩 토크나이저 토큰 수로 max_tokens 이하가 되게 자른다.

    모든 방식이 텍스트를 경계 단위로 쪼갠 뒤 상한까지 앞에서부터 채운다. 방식은 어느 경계에서 쪼개는지만 다르다.
    fixed와 sliding은 같은 단어 단위 창이고, 창을 미는 간격(겹침)으로 구분한다. semantic은 문장 임베딩이 필요하다.
    """

    def __init__(
        self, method: ChunkMethod, max_tokens: int, overlap_tokens: int, count: TokenCounter, offsets: TokenOffsets,
        embed: Embedder | None = None,
    ) -> None:
        if max_tokens <= 0 or not 0 <= overlap_tokens < max_tokens:
            raise ValueError("need max_tokens > 0 and 0 <= overlap_tokens < max_tokens")
        if (method == "semantic") != (embed is not None):
            raise ValueError("embed is required for method='semantic' and only for it")
        self._method = method
        self._max = max_tokens
        self._overlap = overlap_tokens
        self._count = count
        self._offsets = offsets
        self._embed = embed
        # 특수 토큰과 문서 접두어는 청크마다 한 번 붙으므로 본문 예산에서 미리 뺀다.
        self._budget = max_tokens - count("")

    @property
    def name(self) -> str:
        """인덱스 계약과 실험 기록에 쓰는 설정 이름."""
        return f"{self._method}-{self._max}-{self._overlap}"

    def split(self, document: Document) -> list[Chunk]:
        """문서 하나를 순서대로 자른다. 같은 입력이면 같은 청크와 id가 나온다."""
        text = document.text
        # 문서를 한 번만 토큰화하고 구간 길이는 그 안에서 시작하는 토큰 수로 센다. 구간 길이가 더하기로 맞아떨어진다.
        starts = [start for start, _ in self._offsets(text)]
        whole = (0, len(text))
        if self._method in ("fixed", "sliding"):
            windows = self._pack(text, starts, self._spans(starts, whole, text, WORD_BOUNDARIES), self._overlap)
        elif self._method == "recursive":
            windows = self._pack(text, starts, self._spans(starts, whole, text, PARAGRAPH_BOUNDARIES), self._overlap)
        elif self._method == "structure":
            windows = self._by_section(text, starts)
        else:
            windows = self._by_meaning(text, starts)
        chunks: list[Chunk] = []
        for start, end in windows:
            piece = text[start:end].strip()
            if piece:
                chunks.append(Chunk(chunk_id=Chunk.make_id(document.doc_id, piece), doc_id=document.doc_id, ordinal=len(chunks), text=piece))
        return chunks

    def _by_section(self, text: str, starts: list[int]) -> list[Span]:
        """상한 안에 드는 절은 쪼개지 않고 이웃 절과 묶는다. 상한을 넘는 절만 문단 경계로 재귀 분할한다.

        절은 의미 단위라 절 사이에는 겹침을 두지 않는다. 겹침은 한 절을 여러 청크로 나눌 때만 쓴다.
        """
        windows: list[Span] = []
        pending: list[Span] = []
        for section in _sections(text):
            if _size(starts, section) <= self._budget:
                pending.append(section)
                continue
            windows += self._pack(text, starts, pending, 0)
            pending = []
            windows += self._pack(text, starts, self._spans(starts, section, text, PARAGRAPH_BOUNDARIES), self._overlap)
        return windows + self._pack(text, starts, pending, 0)

    def _by_meaning(self, text: str, starts: list[int]) -> list[Span]:
        """문장마다 임베딩하고 이웃 문장 거리가 문서 안 SEMANTIC_PERCENTILE 백분위를 넘는 곳에서 자른다.

        자른 묶음이 상한 안이면 그대로 청크다(작은 묶음을 합치지 않는다). 상한을 넘는 묶음만 문장 단위로 채운다.
        """
        cuts = [m.end() for m in SENTENCE.finditer(text) if 0 < m.end() < len(text)]
        sentences = [
            span for piece in zip([0] + cuts, cuts + [len(text)])
            for span in self._spans(starts, piece, text, PARAGRAPH_BOUNDARIES[1:])
        ]
        if len(sentences) < 2 or self._embed is None:
            return sentences
        vectors = self._embed([text[s:e] for s, e in sentences])
        distances = 1.0 - np.sum(vectors[:-1] * vectors[1:], axis=1)
        threshold = float(np.percentile(distances, SEMANTIC_PERCENTILE))
        groups: list[list[Span]] = [[sentences[0]]]
        for sentence, distance in zip(sentences[1:], distances):
            if distance > threshold:
                groups.append([])
            groups[-1].append(sentence)
        # 상한 안의 묶음은 _pack이 한 청크로 돌려준다. 상한을 넘는 묶음만 여러 청크가 된다.
        return [window for group in groups for window in self._pack(text, starts, group, self._overlap)]

    def _spans(self, starts: list[int], span: Span, text: str, boundaries: tuple[re.Pattern[str], ...]) -> list[Span]:
        """상한을 넘는 구간만 첫 경계로 쪼개고, 그래도 넘는 조각은 다음 경계로 다시 쪼갠다. 경계 문자는 앞 조각에 붙인다."""
        if _size(starts, span) <= self._budget:
            return [span]
        start, end = span
        if not boundaries:
            # 경계가 없는 긴 문자열(긴 URL, 해시)은 토큰 위치에서 자른다.
            inside = [s for s in starts if start < s < end]
            cuts = inside[self._budget - 1::self._budget]
            return list(zip([start] + cuts, cuts + [end]))
        cuts = [m.end() for m in boundaries[0].finditer(text, start, end) if start < m.end() < end]
        if not cuts:
            return self._spans(starts, span, text, boundaries[1:])
        pieces = list(zip([start] + cuts, cuts + [end]))
        return [s for piece in pieces for s in self._spans(starts, piece, text, boundaries[1:])]

    def _pack(self, text: str, starts: list[int], spans: list[Span], overlap: int) -> list[Span]:
        """조각을 앞에서부터 상한까지 채운다. 다음 청크는 직전 청크 끝 조각을 overlap 토큰 이하만큼 다시 가져와 시작한다."""
        sizes = [_size(starts, s) for s in spans]
        windows: list[Span] = []
        first = 0
        while first < len(spans):
            last, total = first, 0
            while last < len(spans) and (last == first or total + sizes[last] <= self._budget):
                total += sizes[last]
                last += 1
            # 구간 토큰 수는 경계 토큰 하나 차이가 날 수 있어, 확정 전에 잘라낸 텍스트를 실제로 세어 넘으면 뒤 조각을 뺀다.
            while last - first > 1 and self._count(text[spans[first][0]:spans[last - 1][1]].strip()) > self._max:
                last -= 1
            windows.append((spans[first][0], spans[last - 1][1]))
            if last >= len(spans):
                break
            carried, next_first = 0, last
            while next_first - 1 > first and carried + sizes[next_first - 1] <= overlap:
                next_first -= 1
                carried += sizes[next_first]
            first = next_first
        return windows


def _size(starts: list[int], span: Span) -> int:
    """구간 안에서 시작하는 토큰 수."""
    return bisect.bisect_left(starts, span[1]) - bisect.bisect_left(starts, span[0])


def _sections(text: str) -> list[Span]:
    """Markdown 제목 줄마다 절을 나눈다. 코드 블록 안의 # 줄(셸 주석)은 제목으로 보지 않는다."""
    starts = [0]
    offset = 0
    in_fence = False
    for line in text.splitlines(keepends=True):
        if FENCE.match(line):
            in_fence = not in_fence
        elif not in_fence and HEADING.match(line) and offset > 0:
            starts.append(offset)
        offset += len(line)
    return list(zip(starts, starts[1:] + [len(text)]))
