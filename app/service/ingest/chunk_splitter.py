"""문서를 청크로 나눈다. 지금은 고정 길이 분할만 있고, 분할 방식은 Chunking 전략 선정 실험에서 정한다."""
from app.schema.chunk_schema import Chunk, Document


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
