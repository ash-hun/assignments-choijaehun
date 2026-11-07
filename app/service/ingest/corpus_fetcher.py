"""manifest로 고정한 Corpus 원문을 받아 로컬에 맞춘다. 다시 실행하면 해시가 맞는 파일은 건너뛴다."""
import json
from pathlib import Path, PurePosixPath
from concurrent.futures import ThreadPoolExecutor

from app.schema.corpus_schema import CorpusFile, CorpusSource, CorpusManifest
from app.common.content_hasher import sha256_bytes
from app.client.github_client import GitHubClient
from app.common.logger import get_logger

logger = get_logger(__name__)


class CorpusFetcher:
    """원천 정의 하나를 받아 원문 디렉토리와 manifest를 같은 상태로 수렴시킨다."""

    def __init__(self, github: GitHubClient, corpus_root: Path, manifest_dir: Path, concurrency: int = 8) -> None:
        self._github = github
        self._corpus_root = corpus_root
        self._manifest_dir = manifest_dir
        self._concurrency = concurrency

    def raw_dir(self, source: CorpusSource) -> Path:
        """원천의 원문이 놓이는 디렉토리."""
        return self._corpus_root / source.name

    def manifest_path(self, source: CorpusSource) -> Path:
        """원천의 manifest 파일 경로."""
        return self._manifest_dir / f"{source.name}.json"

    def sync(self, source: CorpusSource) -> CorpusManifest:
        """manifest가 있으면 그대로 맞추고, 없으면 원격 트리에서 만들어 저장한다."""
        path = self.manifest_path(source)
        if path.exists():
            manifest = CorpusManifest.model_validate_json(path.read_text(encoding="utf-8"))
            if manifest.source != source:
                raise ValueError(f"source definition changed for {source.name}; remove {path} to rebuild")
            self._download_all(source, {f.path: f.sha256 for f in manifest.files})
            logger.info("corpus_verified", name=source.name, files=len(manifest.files))
            return manifest

        rel_paths = self._select_paths(source)
        hashes = self._download_all(source, {p: None for p in rel_paths})
        files = [CorpusFile(path=p, sha256=h, bytes=n) for p, (h, n) in sorted(hashes.items())]
        manifest = CorpusManifest(source=source, files=files)
        self._manifest_dir.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(manifest.model_dump(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)
        logger.info("corpus_manifest_written", name=source.name, files=len(files))
        return manifest

    def _select_paths(self, source: CorpusSource) -> list[str]:
        entries = self._github.list_tree(source.repo, source.commit)
        selected = [
            e.path[len(source.include_prefix):]
            for e in entries
            if e.path.startswith(source.include_prefix) and e.path.endswith(tuple(source.extensions))
        ]
        return sorted(selected)

    def _download_all(self, source: CorpusSource, expected: dict[str, str | None]) -> dict[str, tuple[str, int]]:
        raw_dir = self.raw_dir(source)
        with ThreadPoolExecutor(max_workers=self._concurrency) as pool:
            results = pool.map(lambda p: (p, self._ensure_file(source, raw_dir, p, expected[p])), sorted(expected))
            return dict(results)

    def _ensure_file(self, source: CorpusSource, raw_dir: Path, rel: str, expected_sha: str | None) -> tuple[str, int]:
        target = _safe_target(raw_dir, rel)
        if target.exists():
            data = target.read_bytes()
            digest = sha256_bytes(data)
            # 원문은 고정 commit에서 원자적으로 쓰였으므로 해시가 없으면 로컬 파일을 그대로 믿는다.
            if expected_sha is None or digest == expected_sha:
                return digest, len(data)

        data = self._github.download_file(source.repo, source.commit, source.include_prefix + rel)
        digest = sha256_bytes(data)
        if expected_sha is not None and digest != expected_sha:
            raise ValueError(f"sha256 mismatch for {source.name}/{rel}")
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(target)
        return digest, len(data)


def _safe_target(raw_dir: Path, rel: str) -> Path:
    """원격 경로가 원문 디렉토리 밖을 가리키지 못하게 막는다."""
    pure = PurePosixPath(rel)
    if pure.is_absolute() or ".." in pure.parts or not pure.parts:
        raise ValueError(f"unsafe path: {rel}")
    target = (raw_dir / Path(*pure.parts)).resolve()
    if not target.is_relative_to(raw_dir.resolve()):
        raise ValueError(f"unsafe path: {rel}")
    return target
