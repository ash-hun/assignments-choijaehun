# 아키텍처 설계

기획: `project_planning/plan.md`. 기능과 모듈 매핑의 정본은 `docs/features.md`, 엔드포인트와 파이프라인 계약의 정본은 `docs/api_spec.md`.

## 요약

오프라인 Ingest 경로가 문서를 정제, 청크, 임베딩해 데이터베이스에 저장하고, 온라인 Query 경로가 질문마다 그 인덱스를 검색해 인용 달린 답을 생성하거나 거절한다. 평가 도구는 Query 경로를 직접 호출해 Gold Set 전체를 채점한다.

## 두 경로

```
[Ingest: 쓰기, 오프라인 배치, compose 일회성 서비스]
 make corpus ─▶ corpus_fetcher
 make ingest ─▶ ingest_service ─▶ document_loader ─▶ text_cleaner ─▶ chunk_splitter ─▶ embedding_client ─▶ chunk_repository.upsert
                                                                         │ (text_tokenizer)                         │
                                                                         ▼                                          ▼
                                                              ┌─────────────── 공유 계약 ───────────────┐   벡터 DB 컬렉션
                                                              │ 임베딩 모델, 토크나이저, Chunk 설정 해시 │◀── 메타데이터
                                                              └─────────────────────────────────────────┘
                                                                         ▲
[Query: 읽기, 온라인, FastAPI]                                           │ 기동 시 검증
 POST /v1/query(/stream) ─▶ query_router ─▶ query_service ─▶ chunk_retriever ─▶ evidence_checker ─▶ prompt_builder ─▶ llm_client ─▶ citation_parser
                                                        │ (embedding_client, text_tokenizer, chunk_repository.search)

[Eval: 오프라인, CLI]
 make eval ─▶ eval_service ─▶ query_service(직접 호출) ─▶ 지표 모듈 ─▶ report_writer
```

- 두 경로는 코드 디렉토리부터 나뉜다(`service/ingest/`, `service/query/`). Query 경로는 저장소에 쓰지 않고 `chunk_repository`의 읽기 메서드만 쓴다.
- 두 경로가 공유하는 것은 인덱스와 `common/text_tokenizer.py`, `client/embedding_client.py` 두 모듈뿐이다. 둘 중 하나라도 어긋나면 검색이 조용히 망가지므로, Ingest가 컬렉션 메타데이터에 임베딩 모델, 토크나이저, Chunk 설정 해시를 기록하고 Query가 기동 시 자기 설정과 대조해 다르면 기동을 거부한다.
- Eval은 HTTP를 거치지 않고 `query_service`를 직접 호출한다. HTTP 계층의 지연과 실패가 품질 지표에 섞이지 않게 하고, 서버 없이 단일 명령으로 돌리기 위해서다.

## 실행 단위

| compose 서비스 | 이미지 | 수명 | 명령 |
|---|---|---|---|
| `qdrant` | `qdrant/qdrant:v1.20.0` | 상시 | 기본. 데이터베이스 선정 실험에서 확정. 지금은 실험 profile(`dbbench`)에만 있고 Ingest 구현 때 운영 구성으로 옮김 |
| `api` | 프로젝트 이미지 | 상시 | `uvicorn app.main:app` |
| `batch` | 프로젝트 이미지 `runtime` 단계(api와 같음) | 일회성, `profiles: [batch]` | `python -m <모듈>`. `make corpus`, `make ingest`, `make eval` 등이 감싼다 |
| `dev` | 프로젝트 이미지 `dev` 단계(개발 의존성 포함) | 일회성, `profiles: [dev]`, 네트워크 없음 | `make test`, `make typecheck` |

`batch`는 profile로 묶어 `docker compose up`에서 뜨지 않게 하고 `docker compose run --rm batch <모듈> ...`로만 실행한다. Ingest, 선정 실험, Eval이 모두 이 서비스를 쓴다. api와 같은 이미지 단계를 써서 두 경로의 토크나이저와 임베딩 클라이언트 버전이 갈라지지 않게 한다. `data/`와 `research/`는 호스트 디렉토리를 마운트해 결과가 저장소에 남는다. `dev`는 네트워크를 끊어 테스트가 외부 API를 호출하지 못하게 한다.

## API 서버

- async 엔드포인트와 `AsyncOpenAI`, 벡터 DB async 클라이언트. lifespan에서 클라이언트를 한 번 만들고 인덱스 계약을 검증한 뒤 요청을 받는다.
- LLM 동시 호출은 세마포어로 상한을 둔다. 대기 한도를 넘으면 503과 `Retry-After`를 돌려준다.
- 요청 미들웨어가 `X-Request-ID`를 받거나 만들어 structlog contextvars에 묶고 응답 헤더로 돌려준다. 같은 미들웨어가 처리 시간을 로그로 남긴다.
- `API_KEY` 환경변수가 있으면 `X-API-Key` 헤더를 의존성으로 검사한다. 없으면 로컬 개발용으로 검사를 끈다.
- 예외는 한 곳에서 HTTP 상태로 바꾼다. 업스트림 타임아웃 504, 업스트림 실패 502, 벡터 DB 실패와 동시 호출 상한 초과 503. 응답 본문에는 내부 메시지와 비밀값을 넣지 않는다.
- Streaming은 같은 `query_service`의 생성 단계만 스트림으로 바꾼다. 토큰을 `token` 이벤트로 흘리고, 생성이 끝나면 `citation_parser`로 검증한 인용을 `final` 이벤트로 보낸다.

## 층 구조

진입점(`api`, `cli`)에서 `service`로, `service`에서 `repository`와 `client`로, 맨 아래 `schema`와 `common`. 의존은 이 방향으로만 흐른다. `service` 안에서는 `ingest`, `query`, `eval` 하위 패키지로 경로를 나누고, `eval`은 `query`를 호출할 수 있지만 `ingest`와 `query`는 서로 import하지 않는다.

## 디렉토리 트리

```
.
├── compose.yaml                 # qdrant, api(Query 구현 후 추가), batch(일회성), dev(테스트), 선정 실험 후보 DB(profile dbbench)
├── Dockerfile
├── Makefile                     # corpus, ingest, serve, eval, select, test 별칭
├── pyproject.toml / uv.lock
├── .env.example                 # 키 이름만. 값 없음
├── app/
│   ├── main.py                  # FastAPI 앱 생성, lifespan(클라이언트 조립, 인덱스 계약 검증)
│   ├── api/query_router.py      # /v1/query, /v1/query/stream
│   ├── api/health_router.py     # /health, /ready
│   ├── api/request_middleware.py # 요청 ID, 처리 시간 로그
│   ├── api/api_key_guard.py     # X-API-Key 의존성
│   ├── api/error_mapper.py      # 예외를 HTTP 상태와 에러 본문으로 변환
│   ├── cli/corpus_cli.py
│   ├── cli/ingest_cli.py
│   ├── cli/eval_cli.py          # run, gold-draft, agreement 하위 명령
│   ├── cli/selection_cli.py     # 선정 실험 실행(closed-book, 토크나이저, 임베딩, LLM)
│   ├── service/ingest/
│   │   ├── ingest_service.py
│   │   ├── corpus_fetcher.py
│   │   ├── document_loader.py
│   │   ├── text_cleaner.py
│   │   └── chunk_splitter.py
│   ├── service/query/
│   │   ├── query_service.py
│   │   ├── chunk_retriever.py
│   │   ├── evidence_checker.py
│   │   ├── prompt_builder.py
│   │   └── citation_parser.py
│   ├── service/eval/
│   │   ├── eval_service.py
│   │   ├── gold_set_loader.py
│   │   ├── gold_drafter.py
│   │   ├── retrieval_metric.py
│   │   ├── refusal_metric.py
│   │   ├── judge_metric.py
│   │   ├── agreement_service.py
│   │   ├── agreement_calculator.py
│   │   ├── selection_service.py # 선정 실험 조립. 파이프라인 모듈을 설정만 바꿔 재사용
│   │   └── report_writer.py
│   ├── repository/chunk_repository.py   # 선정된 벡터 DB 구현. ensure_collection, upsert(ingest), search(query)
│   ├── client/llm_client.py
│   ├── client/embedding_client.py
│   ├── client/llm_cache.py
│   ├── schema/query_schema.py
│   ├── schema/chunk_schema.py
│   ├── schema/index_schema.py   # 인덱스 계약(임베딩 모델, 토크나이저, Chunk 설정 해시)
│   ├── schema/gold_schema.py
│   ├── schema/eval_schema.py
│   └── common/logger.py, settings.py, content_hasher.py, text_tokenizer.py
├── prompts/                     # answer_v1.md, judge_faithfulness_v1.md 등. 해시를 결과에 기록
├── configs/                     # baseline.yaml, hybrid.yaml, selection/*.yaml
├── data/
│   ├── corpus/manifest.json     # 원문 URL, 고정 버전, 파일별 sha256
│   ├── corpus/raw/              # 다운로드 결과. 라이선스에 따라 커밋 여부 결정
│   └── gold/dev_set.jsonl, test_set.jsonl, human_labels.jsonl
├── research/                    # 선정 실험 기록. 질문, 후보, 방법, 결과, 결정, 재현 명령
│   ├── dataset_selection.md
│   ├── database_selection.md
│   ├── embedding_selection.md
│   ├── tokenizer_selection.md
│   ├── chunking_selection.md
│   ├── refusal_threshold.md
│   ├── llm_selection.md
│   └── gold_metric_selection.md
├── reports/<run_id>/            # results.jsonl, summary.md. 제출 근거라 커밋
├── tests/unit/, tests/integ/
└── docs/features.md, api_spec.md
```

## 상태 저장 위치

| 상태 | 쓰는 경로 | 위치 | 자연 키 | 재실행 시 |
|---|---|---|---|---|
| 원문 | Ingest | `data/corpus/raw/` | 파일 경로 + sha256 | 해시가 같으면 다시 받지 않음 |
| Chunk와 벡터 | Ingest | 벡터 DB 컬렉션 `chunks_<corpus해시8>_<chunk설정해시8>_<임베딩모델>` | chunk_id = sha256(doc_id, section_path, text) | upsert로 같은 상태로 수렴 |
| 인덱스 계약 | Ingest | 컬렉션 메타데이터 | 컬렉션 이름 | 같은 값으로 덮어씀 |
| LLM 응답 캐시 | Query, Eval | `.cache/llm.sqlite` | sha256(모델, 메시지, temperature, seed) | 캐시 적중 시 호출 0회 |
| 평가 결과 | Eval | `reports/<run_id>/` | run_id = sha256(설정, git hash, gold 해시, 프롬프트 해시) 앞 12자 | 같은 디렉토리를 덮어써 수렴 |

컬렉션 이름에 Chunk 설정 해시와 임베딩 모델을 넣는 이유: 설정을 바꾸면 이전 설정의 Chunk가 같은 컬렉션에 남아 검색을 오염시킨다. 설정마다 컬렉션을 분리하면 선정 실험과 Part C에서 여러 설정을 나란히 비교할 수 있고 삭제 로직도 필요 없다.

LLM 캐시는 운영 Query 경로에서는 끈다. 운영에서 같은 질문에 같은 답을 고정할 이유가 없고, 캐시는 평가 재현과 비용 절감을 위한 장치다.

## 외부 연동

| 대상 | 경로 | 용도 | 보호 장치 |
|---|---|---|---|
| 엘리스 ML API (OpenAI 호환) | Query, Eval | 답변 생성, Judge, Gold 초안 | 타임아웃 60초, 재시도 3회, 키는 `SecretStr` 환경변수. 확인된 제약: `gpt-6.1-terra`는 temperature 기본값(1)만 허용, 비스트리밍 호출은 `max_completion_tokens` 2000 이하, `max_tokens` 대신 `max_completion_tokens` 사용, JSON Schema 구조화 출력 지원 |
| 로컬 임베딩 모델(fastembed, ONNX) | Ingest, Query | Chunk와 질의 벡터화. 잠정 `Qwen/Qwen3-Embedding-0.6B`(엘리스 모델 라이브러리에 임베딩 모델이 없어 로컬 실행) | 외부 호출 없음. 모델 파일은 `.cache/models`에 받아 재사용 |
| Qdrant | Ingest(쓰기), Query(읽기) | dense, sparse(IDF) 저장과 검색, RRF 결합 검색 | gRPC 연결(REST는 응답마다 약 45ms 지연 관찰), compose 내부 네트워크, Ingest 시 `ensure_collection` |
| Corpus 원천 | Ingest | 다운로드 | 허용 URL은 manifest에만. 사용자 입력 URL 호출 없음 |

## 핵심 설계 결정

- **Ingest는 질의 경로 밖의 배치, HTTP 미노출**: 질의마다 Ingest를 돌리면 지연과 비용이 Corpus 크기에 비례한다. HTTP로 열지 않으므로 공개 API는 읽기 전용 Query뿐이고, 평가 중 인덱스가 바뀌어 Before/After 비교가 무너질 경로가 없다. 실행은 compose 일회성 서비스로 해 재현 절차를 compose 하나로 끝낸다. 문서 단위 증분 Ingest API(비동기 작업, API Key 인증, 동시 Ingest 잠금)는 README 향후 과제에 설계로 남긴다.
- **인덱스 계약 검증**: 임베딩 모델이나 토크나이저가 색인과 질의에서 다르면 에러 없이 검색 품질만 떨어진다. 기동 시점에 실패시키는 편이 원인 추적이 쉽다.
- **LangChain 미사용**: 검색, 프롬프트 조립, 인용 파싱을 직접 구현한다. 면접에서 단계별 동작을 설명할 수 있고, 평가할 때 중간 산출물을 그대로 기록할 수 있다.
- **LangGraph 미도입**: 분기 없는 고정 순서 파이프라인이라 에이전트가 아니다.
- **거절 두 단계**: dense 최고 점수가 임계값 미만이면 LLM을 부르지 않는다. 넘으면 프롬프트의 근거 부족 토큰으로 판정한다. hybrid 검색에서도 1차 판정은 dense 점수로 한다. RRF 점수는 순위 기반이라 임계값을 둘 수 없고, 검색 방식을 바꿀 때 거절 동작이 함께 바뀌지 않게 하기 위해서다. 임계값은 dev set 점수 분포로 보정한다.
- **Citation 검증**: 모델이 낸 `[n]` 중 실제 제공한 근거 번호만 인정하고, 버린 개수를 `meta.dropped_citations`로 기록한다.
- **Hybrid 검색은 설정 스위치**: `retrieval.mode: dense | hybrid`. Before/After 비교의 변인을 하나로 유지한다.
- **선정 실험은 파이프라인 재사용**: 선정 실험 전용 검색, 임베딩 코드를 따로 두지 않는다. 같은 모듈을 설정만 바꿔 돌려야 선정 결과가 실제 서비스에 그대로 옮겨진다.

## 선정 결과에 따라 확정되는 지점

| 지점 | 결정하는 선정 실험 |
|---|---|
| `document_loader` 파서 | 데이터셋 |
| `common/text_tokenizer.py` 청크 길이 단위, BM25 토큰화 | 토크나이저 |
| `chunk_splitter` 분할 방식, 크기, 겹침 | Chunking 전략 |
| `chunk_repository` 구현, compose 벡터 DB 서비스, 컬렉션 명명 방식 | 데이터베이스(확정: Qdrant, `app/repository/qdrant_chunk_repository.py`) |
| `embedding_client` 모델과 호출 방식(API 또는 로컬) | Embedding(잠정: Qwen3-Embedding-0.6B, 로컬 fastembed. 2위 multilingual-e5-large와 교차 확인 예정) |
| `llm_client` 생성 모델 | LLM |
| `llm_client` Judge 모델 | Gold Set 및 Metric(Part B) |
| `judge_metric` 지표 목록과 루브릭 | Gold Set 및 Metric |
| `evidence_checker` 임계값 | 거절 임계값 보정 |
