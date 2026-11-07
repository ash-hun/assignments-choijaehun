"""GitHub에서 고정 commit의 파일 트리와 원문을 받는 클라이언트."""
import httpx
from urllib.parse import quote

from app.schema.corpus_schema import TreeEntry
from app.common.logger import get_logger

API_BASE = "https://api.github.com"
RAW_BASE = "https://raw.githubusercontent.com"
USER_AGENT = "elice-rag-qa-corpus-fetcher"
MAX_FILE_BYTES = 5_000_000

logger = get_logger(__name__)


class GitHubClient:
    """commit SHA로 고정된 경로만 호출한다. 사용자 입력 URL은 받지 않는다."""

    def __init__(self, http: httpx.Client, token: str | None = None) -> None:
        self._http = http
        self._headers = {"User-Agent": USER_AGENT}
        if token:
            self._headers["Authorization"] = f"Bearer {token}"

    def list_tree(self, repo: str, commit: str) -> list[TreeEntry]:
        """commit 시점의 전체 파일 트리를 돌려준다."""
        url = f"{API_BASE}/repos/{repo}/git/trees/{commit}?recursive=1"
        response = self._http.get(url, headers={**self._headers, "Accept": "application/vnd.github+json"})
        response.raise_for_status()
        body = response.json()
        if body.get("truncated"):
            raise RuntimeError(f"tree truncated for {repo}@{commit}")
        return [TreeEntry(path=t["path"], size=t.get("size", 0)) for t in body["tree"] if t["type"] == "blob"]

    def download_file(self, repo: str, commit: str, path: str) -> bytes:
        """commit 시점의 파일 원문을 받는다. 크기 상한을 넘으면 거부한다."""
        url = f"{RAW_BASE}/{repo}/{commit}/{quote(path)}"
        response = self._http.get(url, headers=self._headers)
        response.raise_for_status()
        if len(response.content) > MAX_FILE_BYTES:
            raise ValueError(f"file too large: {path}")
        return response.content
