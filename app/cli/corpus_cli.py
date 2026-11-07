"""Corpus 후보 원문 받기(fetch)와 통계(profile) 명령. 데이터셋 선정 실험의 진입점이다."""
import sys
import json
import httpx
import argparse
from pathlib import Path

from app.service.eval.corpus_profiler import profile_corpus
from app.service.ingest.corpus_fetcher import CorpusFetcher
from app.client.github_client import GitHubClient
from app.schema.corpus_schema import CorpusSource
from app.common.settings import get_settings
from app.common.logger import get_logger

CANDIDATES_FILE = "corpus/candidates.json"
PROFILE_FILE = "artifacts/dataset_profile.json"

logger = get_logger(__name__)


def load_sources(data_dir: Path, names: list[str] | None) -> list[CorpusSource]:
    """후보 정의 파일을 읽고 이름으로 거른다."""
    raw = json.loads((data_dir / CANDIDATES_FILE).read_text(encoding="utf-8"))
    sources = [CorpusSource.model_validate(item) for item in raw]
    if names:
        unknown = set(names) - {s.name for s in sources}
        if unknown:
            raise SystemExit(f"unknown corpus: {sorted(unknown)}")
        sources = [s for s in sources if s.name in names]
    return sources


def build_fetcher() -> CorpusFetcher:
    """설정에서 클라이언트와 경로를 조립한다."""
    settings = get_settings()
    token = settings.github_token.get_secret_value() if settings.github_token else None
    http = httpx.Client(timeout=settings.http_timeout_seconds, follow_redirects=False)
    return CorpusFetcher(
        github=GitHubClient(http, token),
        corpus_root=settings.data_dir / "corpus" / "raw",
        manifest_dir=settings.data_dir / "corpus" / "manifests",
        concurrency=settings.download_concurrency,
    )


def main(argv: list[str] | None = None) -> int:
    """fetch는 원문과 manifest를 맞추고, profile은 후보 통계를 JSON으로 남긴다."""
    parser = argparse.ArgumentParser(prog="corpus")
    parser.add_argument("command", choices=["fetch", "profile"])
    parser.add_argument("--name", action="append", help="대상 후보 이름. 생략하면 전부")
    args = parser.parse_args(argv)

    settings = get_settings()
    sources = load_sources(settings.data_dir, args.name)
    fetcher = build_fetcher()

    if args.command == "fetch":
        for source in sources:
            fetcher.sync(source)
        return 0

    profiles = [profile_corpus(fetcher.sync(s), fetcher.raw_dir(s)).model_dump() for s in sources]
    out = settings.research_dir / PROFILE_FILE
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(profiles, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    logger.info("profile_written", path=str(out), corpora=len(profiles))
    return 0


if __name__ == "__main__":
    sys.exit(main())
