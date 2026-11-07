"""Corpus 원천 정의, 고정된 파일 목록(manifest), 데이터셋 통계 모델."""
from typing import Literal
from pydantic import BaseModel, Field

Language = Literal["ko", "en"]


class CorpusSource(BaseModel):
    """GitHub 저장소의 특정 commit, 특정 경로 아래 문서를 하나의 Corpus 후보로 정의한다."""

    name: str = Field(pattern=r"^[a-z0-9_]{1,64}$")
    repo: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    include_prefix: str = Field(min_length=1, max_length=256)
    extensions: list[str] = Field(min_length=1)
    license: str
    language: Language
    description: str


class CorpusFile(BaseModel):
    """manifest에 고정된 원문 파일 하나. path는 include_prefix 기준 상대 경로다."""

    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bytes: int = Field(ge=0)


class CorpusManifest(BaseModel):
    """원천 정의와 파일별 해시. 이 파일이 있으면 누구나 같은 원문을 받을 수 있다."""

    source: CorpusSource
    files: list[CorpusFile]


class TreeEntry(BaseModel):
    """원격 저장소 트리의 파일 하나."""

    path: str
    size: int = Field(ge=0)


class CorpusProfile(BaseModel):
    """데이터셋 선정 실험에서 후보를 비교하는 정량 통계."""

    name: str
    language: Language
    license: str
    commit: str
    documents: int
    total_chars: int
    estimated_pages: float
    median_doc_chars: int
    stub_documents: int
    heading_depth_counts: dict[int, int]
    max_heading_depth: int
    code_char_ratio: float
    table_line_ratio: float
    markup_noise_per_doc: float
    version_mentions_per_doc: float
    internal_links_per_doc: float
    linked_doc_ratio: float
    duplicate_title_ratio: float
