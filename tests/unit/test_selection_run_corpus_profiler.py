"""selection_run 기능의 데이터셋 통계(corpus_profiler) 단위 테스트."""
from pathlib import Path

from app.schema.corpus_schema import CorpusFile, CorpusSource, CorpusManifest
from app.service.eval.corpus_profiler import profile_corpus

DOC = """---
title: sample
---
# Title
## Section
Requires v1.2.3 or later. {{< note >}} See [other](./b.md) and [site](https://x.io).
| a | b |
```
code line
```
"""


def make_manifest(paths: list[str]) -> CorpusManifest:
    source = CorpusSource(
        name="sample", repo="owner/repo", commit="b" * 40, include_prefix="docs/",
        extensions=[".md"], license="MIT", language="en", description="test",
    )
    return CorpusManifest(source=source, files=[CorpusFile(path=p, sha256="0" * 64, bytes=0) for p in paths])


def test_profile_counts_structure_outside_code_and_front_matter(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text(DOC, encoding="utf-8")

    profile = profile_corpus(make_manifest(["a.md"]), tmp_path)

    assert profile.documents == 1
    assert profile.heading_depth_counts == {1: 1, 2: 1}
    assert profile.max_heading_depth == 2
    assert profile.version_mentions_per_doc == 1.0
    assert profile.markup_noise_per_doc == 1.0
    assert profile.code_char_ratio > 0
    assert profile.stub_documents == 1


def test_profile_counts_internal_links_and_duplicate_titles(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text(DOC, encoding="utf-8")
    (tmp_path / "b.md").write_text("# Same\nbody [x](#anchor)", encoding="utf-8")
    (tmp_path / "c.md").write_text("# Same { #same }\nbody", encoding="utf-8")

    profile = profile_corpus(make_manifest(["a.md", "b.md", "c.md"]), tmp_path)

    assert profile.internal_links_per_doc == round(1 / 3, 2)
    assert profile.linked_doc_ratio == round(1 / 3, 3)
    assert profile.duplicate_title_ratio == round(2 / 3, 3)


def test_profile_of_empty_manifest_is_zero(tmp_path: Path) -> None:
    profile = profile_corpus(make_manifest([]), tmp_path)

    assert profile.documents == 0
    assert profile.total_chars == 0
    assert profile.max_heading_depth == 0
