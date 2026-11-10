"""환경변수에서 실행 설정을 읽는 공통 모듈. 비밀값은 SecretStr로만 다룬다."""
from pathlib import Path
from pydantic import SecretStr
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.schema.vector_schema import IndexContract
from app.schema.query_schema import RetrievalMode
from app.common.text_tokenizer import SplitMode

# Qwen3-Embedding 모델 카드의 질의 지시문 형식. 선정 실험과 Query 경로가 같은 문구를 쓴다.
QWEN_QUERY_PREFIX = (
    "Instruct: Given a question about the uv Python package manager, "
    "retrieve documentation passages that answer the question\nQuery: "
)


class Settings(BaseSettings):
    """프로젝트 전역 설정. 값은 환경변수나 .env에서 온다."""

    # 빈 값(API_KEY=)은 설정하지 않은 것으로 본다. 빈 문자열 키로 인증이 켜지거나 빈 URL로 호출하지 않게 한다.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", env_ignore_empty=True)

    data_dir: Path = Path("data")
    research_dir: Path = Path("research")
    github_token: SecretStr | None = None
    http_timeout_seconds: float = 30.0
    download_concurrency: int = 8
    # 데이터셋 선정 실험(research/dataset_selection.md)에서 확정한 Corpus.
    corpus_name: str = "uv_docs"
    gold_seed: int = 2026

    # Query 경로와 Ingest의 확정 구성(research/*_selection.md). 바꾸면 인덱스 계약이 달라져 새 컬렉션이 생긴다.
    embedding_model: str = "Qwen/Qwen3-Embedding-0.6B"
    embedding_query_prefix: str = QWEN_QUERY_PREFIX
    bm25_tokenizer: SplitMode = "word"
    chunk_method: str = "structure"
    chunk_size: int = 512
    chunk_overlap: int = 77
    refusal_threshold: float = 0.6375
    default_top_k: int = 5
    # 검색 방식(project_planning/experiments/12_hybrid_fusion.md). Part C 결과로 영어 질의는 CC, 한국어 질의는 dense(routed).
    # 융합 후보 수와 RRF k, CC alpha는 조정하지 않은 기본값이다.
    retrieval_mode: RetrievalMode = "routed"
    fusion_pool: int = 40
    rrf_k: int = 60
    cc_alpha: float = 0.5
    # 생성 모델(research/llm_selection.md). seed를 거부하는 모델이라 보내지 않는다.
    answer_llm_model: str = "claude-haiku-5-5"
    answer_llm_base_url: str | None = None
    answer_temperature: float | None = 0.0
    answer_seed: int | None = None
    answer_max_tokens: int = 1500
    # 동시 호출 상한(llm_concurrency)에서 이 시간 넘게 기다리면 503을 돌려준다.
    llm_queue_timeout_seconds: float = 10.0
    # 답변 모델 단가(100만 토큰당 원, VAT 별도). research/llm_selection.md의 엘리스 Serverless 요금.
    answer_input_krw_per_mtok: float = 141.0
    answer_output_krw_per_mtok: float = 708.0
    # 평가 기록 저장소(compose의 evaldb). 내부 네트워크 전용이고 비밀번호는 EVAL_DB_PASSWORD로만 받는다.
    eval_db_host: str = "evaldb"
    eval_db_port: int = 5432
    eval_db_name: str = "eval"
    eval_db_user: str = "eval"
    eval_db_password: SecretStr | None = None
    reports_dir: Path = Path("reports")
    # 실시간 질의 내역과 대시보드 기준선 스냅샷. API가 시작할 때 저장소에 없는 행만 넣는다(make seed-export로 만든다).
    history_seed_path: Path = Path("data/seed/evaldb_seed.jsonl")
    # Judge 모델(research/gold_metric_selection.md). 답변 모델과 계열이 다르다. 엔드포인트가 없으면 LLM_CANDIDATE_URLS에서 찾는다.
    judge_llm_model: str = "gemini-3.8-flash"
    judge_llm_base_url: str | None = None
    judge_input_krw_per_mtok: float = 1063.0
    judge_output_krw_per_mtok: float = 5315.0
    judge_cache_path: Path = Path(".cache/judge_responses.jsonl")
    # 실시간 누적 평가(research/gold_metric_selection.md). 저장소 비밀번호나 Judge 엔드포인트가 없으면 꺼진 채로 서비스만 뜬다.
    live_eval_enabled: bool = True
    live_judge_sample_rate: float = 1.0
    live_judge_budget_krw: float = 3000.0
    live_snapshot_limit: int = 2000
    # 컨테이너 안에는 .git이 없어 Makefile이 넘긴다. Report와 manifest에 기록만 하고 run_id에는 넣지 않는다.
    git_commit: str = "unknown"
    # 설정되면 /v1/* 요청에 X-API-Key가 필요하다. 없으면 로컬 개발용으로 검사하지 않는다.
    api_key: SecretStr | None = None

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


    def index_contract(self) -> IndexContract:
        """Ingest가 기록하고 Query가 기동 시 대조하는 계약. 두 경로가 같은 함수로 만든다."""
        chunk_config = f"{self.chunk_method}-{self.chunk_size}-{self.chunk_overlap}"
        return IndexContract(embedding_model=self.embedding_model, tokenizer=self.bm25_tokenizer, chunk_config_hash=chunk_config)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """프로세스당 한 번 읽은 설정을 돌려준다."""
    return Settings()
