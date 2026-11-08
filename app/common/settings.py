"""환경변수에서 실행 설정을 읽는 공통 모듈. 비밀값은 SecretStr로만 다룬다."""
from pathlib import Path
from pydantic import SecretStr
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """프로젝트 전역 설정. 값은 환경변수나 .env에서 온다."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    data_dir: Path = Path("data")
    research_dir: Path = Path("research")
    github_token: SecretStr | None = None
    http_timeout_seconds: float = 30.0
    download_concurrency: int = 8
    # 데이터셋 선정 실험(research/dataset_selection.md)에서 확정한 Corpus.
    corpus_name: str = "uv_docs"
    gold_seed: int = 2026

    # 데이터베이스 선정 실험 후보. compose 내부 네트워크 주소이고 외부로 포트를 열지 않는다.
    qdrant_url: str = "http://qdrant:6333"
    postgres_dsn: str = "postgresql://postgres@pgvector:5432/postgres"
    chroma_host: str = "chroma"
    chroma_port: int = 8000
    model_cache_dir: Path = Path(".cache/models")
    # Embedding 선정 전 임시 모델. 로컬 ONNX라 API 비용이 없다.
    bench_embedding_model: str = "BAAI/bge-small-en-v1.5"

    # 엘리스 ML API는 모델마다 엔드포인트가 달라 base URL과 모델명을 함께 받는다.
    elice_serverless_api_key: SecretStr | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = 3
    llm_concurrency: int = 4
    llm_seed: int = 42
    # gpt-6.1-terra처럼 기본값(1) 외 temperature를 거부하는 모델이 있어 기본은 보내지 않는다.
    llm_temperature: float | None = None
    # LLM 선정 실험 후보의 엔드포인트. 모델명을 키로 하는 JSON(LLM_CANDIDATE_URLS)이고 저장소에 두지 않는다.
    llm_candidate_urls: dict[str, str] = {}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """프로세스당 한 번 읽은 설정을 돌려준다."""
    return Settings()
