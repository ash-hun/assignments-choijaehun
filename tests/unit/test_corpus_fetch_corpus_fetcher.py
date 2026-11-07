"""corpus_fetch 기능의 CorpusFetcher 단위 테스트. GitHub 호출은 MockTransport로 대체한다."""
import json
import httpx
import pytest
from pathlib import Path

from app.service.ingest.corpus_fetcher import CorpusFetcher, _safe_target
from app.common.content_hasher import sha256_bytes
from app.client.github_client import GitHubClient
from app.schema.corpus_schema import CorpusSource

COMMIT = "a" * 40
FILES = {"docs/a.md": b"# A\nalpha", "docs/sub/b.md": b"# B\nbeta", "docs/skip.png": b"x", "other/c.md": b"c"}


class FakeGitHub:
    def __init__(self, files: dict[str, bytes]) -> None:
        self.files = files
        self.raw_calls = 0

    def handle(self, request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.github.com":
            tree = [{"path": p, "type": "blob", "size": len(b)} for p, b in self.files.items()]
            return httpx.Response(200, json={"tree": tree, "truncated": False})
        self.raw_calls += 1
        path = request.url.path.split(f"/{COMMIT}/", 1)[1]
        return httpx.Response(200, content=self.files[path])


def make_source() -> CorpusSource:
    return CorpusSource(
        name="sample", repo="owner/repo", commit=COMMIT, include_prefix="docs/",
        extensions=[".md"], license="MIT", language="en", description="test",
    )


def make_fetcher(tmp_path: Path, fake: FakeGitHub) -> CorpusFetcher:
    client = GitHubClient(httpx.Client(transport=httpx.MockTransport(fake.handle)))
    return CorpusFetcher(client, tmp_path / "raw", tmp_path / "manifests", concurrency=2)


def test_sync_writes_manifest_with_only_prefixed_markdown(tmp_path: Path) -> None:
    fake = FakeGitHub(dict(FILES))
    manifest = make_fetcher(tmp_path, fake).sync(make_source())

    assert [f.path for f in manifest.files] == ["a.md", "sub/b.md"]
    assert manifest.files[0].sha256 == sha256_bytes(FILES["docs/a.md"])
    saved = json.loads((tmp_path / "manifests" / "sample.json").read_text(encoding="utf-8"))
    assert saved["files"][1]["path"] == "sub/b.md"
    assert (tmp_path / "raw" / "sample" / "sub" / "b.md").read_bytes() == FILES["docs/sub/b.md"]


def test_sync_twice_downloads_nothing_new(tmp_path: Path) -> None:
    fake = FakeGitHub(dict(FILES))
    fetcher = make_fetcher(tmp_path, fake)
    first = fetcher.sync(make_source())
    calls_after_first = fake.raw_calls

    second = fetcher.sync(make_source())

    assert second == first
    assert fake.raw_calls == calls_after_first


def test_sync_rejects_upstream_content_that_differs_from_manifest(tmp_path: Path) -> None:
    fake = FakeGitHub(dict(FILES))
    fetcher = make_fetcher(tmp_path, fake)
    fetcher.sync(make_source())
    (tmp_path / "raw" / "sample" / "a.md").unlink()
    fake.files["docs/a.md"] = b"tampered"

    with pytest.raises(ValueError, match="sha256 mismatch"):
        fetcher.sync(make_source())


@pytest.mark.parametrize("rel", ["../escape.md", "/etc/passwd", "a/../../b.md"])
def test_safe_target_rejects_paths_outside_raw_dir(tmp_path: Path, rel: str) -> None:
    with pytest.raises(ValueError, match="unsafe path"):
        _safe_target(tmp_path, rel)
