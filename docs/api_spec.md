# RAG QA API 명세

| 항목 | 값 |
|---|---|
| Base URL | `http://localhost:8000` |
| 데이터 포맷 | JSON (UTF-8) |
| 인증 | `API_KEY` 환경변수가 설정되면 `/v1/*`에 `X-API-Key` 헤더 필수. 비어 있으면 없음 |

---

## 개요

시스템은 두 파이프라인으로 나뉜다. Ingest 파이프라인은 오프라인 쓰기 경로로 CLI로만 실행하고 HTTP로 노출하지 않는다. Query 파이프라인은 온라인 읽기 경로로 HTTP API를 제공한다. 데이터의 정본은 `data/corpus/raw/`의 원문이고, 벡터 DB 인덱스는 Ingest가 만든 그 투영이다.

| 파이프라인 | 경로 | 흐름 | 진입점 | 저장소 접근 |
|---|---|---|---|---|
| Ingest | 쓰기, 오프라인 배치 | 문서, 정제, 청크, 임베딩, 인덱스 저장 | `make corpus`, `make ingest` (compose 일회성 서비스) | 쓰기 |
| Query | 읽기, 온라인 | 질문, 검색, LLM 답변 생성, Citation 반환 | FastAPI `POST /v1/query`, `POST /v1/query/stream` | 읽기 전용 |

두 파이프라인의 연결점은 인덱스 계약이다. Ingest가 컬렉션 메타데이터에 기록한 임베딩 모델, 토크나이저, Chunk 설정 해시가 Query의 설정과 다르면 Query 서버는 기동하지 않는다.

---

## Ingest 파이프라인 (오프라인, CLI)

### 단계

| 순서 | 단계 | 입력 | 출력 | 모듈 |
|---|---|---|---|---|
| 1 | 문서 수집 | `data/corpus/manifest.json` | `data/corpus/raw/` 원문 | `corpus_fetcher` |
| 2 | 정제 | 원문 | Document(doc_id, title, url, section 경로, 본문) | `document_loader`, `text_cleaner` |
| 3 | 청크 | Document | Chunk(chunk_id, doc_id, section_path, text, 토큰 수) | `chunk_splitter`, `text_tokenizer` |
| 4 | 임베딩 | Chunk 텍스트 | Dense 벡터(hybrid면 Sparse 벡터 추가) | `embedding_client`, `text_tokenizer` |
| 5 | 인덱스 저장 | Chunk와 벡터 | 벡터 DB 컬렉션, 인덱스 계약 메타데이터 | `chunk_repository` |

### 명령

| 명령 | 실제 실행 | 설명 | 실패 시 |
|---|---|---|---|
| `make corpus` | `docker compose run --rm batch app.cli.corpus_cli fetch` | manifest 기준 원문 다운로드와 sha256 검증 | 해시 불일치 파일 이름을 출력하고 종료 코드 1 |
| `make ingest` | `docker compose up -d qdrant` 후 `docker compose run --rm batch app.cli.ingest_cli` | 정제부터 인덱스 저장, 사라진 청크 삭제까지 | 예외를 출력하고 종료 코드 1. 이미 저장된 Chunk는 유지 |
| `make serve` | `docker compose up -d --build api` | API 서버 기동(`127.0.0.1:8000`) | 인덱스 계약이 다르거나 컬렉션이 없으면 기동 실패 |

`batch` 서비스는 API 서버와 같은 이미지를 쓰고 `profiles: [batch]`로 묶여 `docker compose up`에서는 뜨지 않는다. HTTP로는 노출하지 않는다. 문서 단위 증분 Ingest API는 미구현이며 README 향후 과제에 설계만 둔다.

### 재실행하면

- `make corpus`: 해시가 같은 파일은 다시 받지 않는다.
- `make ingest`: chunk_id가 내용 해시라 upsert로 같은 상태로 수렴하고, 이번 실행에 없는 청크는 지운다. 중간에 죽으면 다시 실행하면 된다. 컬렉션 이름은 인덱스 계약(임베딩 모델, BM25 토크나이저, Chunk 설정)의 해시(`chunks_<corpus>_<해시8>`)라, 설정을 바꾸면 새 컬렉션이 생기고 기존 컬렉션은 그대로 남는다.

---

## Query 파이프라인 (온라인, HTTP)

### 단계

| 순서 | 단계 | 입력 | 출력 | 모듈 |
|---|---|---|---|---|
| 1 | 질문 수신 | 요청 본문 | 검증된 `QueryRequest` | `query_router` |
| 2 | 검색 | 질문 | top-k Chunk와 dense 점수 | `chunk_retriever`, `embedding_client`, `qdrant_chunk_repository` |
| 3 | 근거 충분성 판정 | 검색 점수 | 계속 또는 거절 | `evidence_checker` |
| 4 | LLM 답변 생성 | 번호 매긴 근거와 질문 | `[n]` 인용이 들어간 답변 또는 근거 부족 토큰 | `prompt_builder`, `llm_gate`, `llm_client`, `evidence_checker` |
| 5 | Citation 반환 | 답변과 근거 | 검증된 인용 목록, `QueryResponse` | `citation_parser` |

### 공통 규약

**에러 응답**

```json
{ "detail": "사람이 읽을 수 있는 메시지" }
```

| 상태 코드 | 언제 |
|---|---|
| 200 | 정상. 근거 부족으로 답하지 않은 경우도 200이며 `status`로 구분 |
| 401 | `API_KEY`가 설정됐는데 `X-API-Key`가 없거나 틀림 |
| 422 | 요청 본문이 스키마에 맞지 않음 |
| 502 | LLM 엔드포인트 호출 실패(재시도 소진) |
| 503 | 벡터 DB 연결 실패, 또는 LLM 동시 호출 상한 대기 한도 초과(`Retry-After` 포함) |
| 504 | LLM 엔드포인트 타임아웃 |

에러 본문에는 내부 예외 메시지, 스택, 비밀값을 넣지 않는다. 대신 `X-Request-ID`로 서버 로그를 찾는다.

**페이지네이션**: 없음. 응답 크기가 `top_k` 상한 20으로 묶인다.

**공통 헤더**

| 헤더 | 방향 | 설명 |
|---|---|---|
| `X-Request-ID` | 요청, 응답 | 요청 값이 `[A-Za-z0-9._-]{1,128}`이면 그대로 쓰고, 없거나 형식이 다르면 서버가 만든다(32자 hex). 모든 로그에 붙고 응답 헤더로 돌아온다 |
| `X-API-Key` | 요청 | `API_KEY` 환경변수가 설정된 경우에만 필수. `/health`, `/ready`는 검사하지 않음 |

### 엔드포인트 목록

| Method | Path | 설명 | 상태 |
|---|---|---|---|
| `GET` | `/health` | 프로세스 생존 확인. 항상 200 | 구현됨 |
| `GET` | `/ready` | 벡터 DB 연결과 인덱스 계약 일치 시 200, 아니면 503 | 구현됨 |
| `POST` | `/v1/query` | 질의응답 | 구현됨 |
| `POST` | `/v1/query/stream` | 질의응답 SSE 스트리밍 | 구현됨 |

### POST /v1/query

질문을 받아 근거 기반 답변과 인용을 돌려주거나, 근거가 부족하면 답하지 않는다.

#### Request Body

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|---|---|---|---|---|
| `question` | string | 예 | 없음 | 1자 이상 1000자 이하 |
| `top_k` | int | 아니오 | 5(서버 설정 `DEFAULT_TOP_K`) | 1 이상 20 이하. LLM에 넣는 근거 청크 수 |

#### Response Body

| 필드 | 타입 | 설명 |
|---|---|---|
| `status` | `"answered"` \| `"insufficient_context"` | 답변 여부 |
| `answer` | string | 답변 본문(존재하지 않는 인용 번호는 지움). 거절 시 고정 안내 문구 |
| `citations[].ref` | int | 본문의 `[n]` 번호 |
| `citations[].doc_id` | string | 문서 식별자 |
| `citations[].title` | string | 문서 제목 |
| `citations[].url` | string | 색인한 판(고정 commit)의 GitHub 원문 위치 |
| `citations[].chunk_id` | string | 근거 Chunk 식별자 |
| `citations[].snippet` | string | 근거 청크 앞 300자 |
| `meta.model` | string | 생성 모델 |
| `meta.embedding_model` | string | Embedding 모델 |
| `meta.retrieval_scores` | float[] | 검색 청크의 dense 코사인 유사도(내림차순) |
| `meta.dropped_citations` | int | 존재하지 않는 번호라 버린 인용 수 |
| `meta.latency_ms` | int | 서버 처리 시간 |
| `meta.retrieval_ms` | int \| null | 질의 임베딩과 벡터 검색에 걸린 시간. `latency_ms`와 `first_token_ms`에 포함된다 |
| `meta.usage` | object | `input_tokens`, `output_tokens`. 검색 단계에서 거절하면 0 |
| `meta.first_token_ms` | int \| null | 스트리밍 응답에서 첫 `token` 이벤트까지 걸린 시간(검색 포함). 비스트리밍이나 토큰이 없으면 null |

#### 재호출하면

읽기 전용이라 서버 상태가 바뀌지 않는다. 같은 질문과 같은 인덱스면 검색 결과와 검색 단계 거절 여부는 같다. 생성은 temperature 0이지만 생성 모델(claude-haiku-5-5)이 seed를 받지 않아, 모델 제공자 측 비결정성 때문에 문구가 달라질 수 있다.

### POST /v1/query/stream

`/v1/query`와 같은 요청 본문을 받아 `text/event-stream`으로 응답한다.

#### 이벤트

| event | data | 언제 |
|---|---|---|
| `token` | `{ "text": str }` | 생성 토큰마다 |
| `final` | `/v1/query` Response Body와 같은 구조 | 생성 종료 후 한 번. 검색 단계에서 거절되면 `token` 없이 이것만 |
| `error` | `{ "detail": str, "status_code": int }` | 스트림 시작 후 업스트림 실패나 타임아웃. 이후 연결 종료 |

첫 이벤트 전에 난 에러(401, 422, 검색 실패와 동시 호출 상한 초과 503, 첫 토큰 전 LLM 실패 502와 타임아웃 504)는 일반 HTTP 에러로 응답한다. `token`으로 흘린 텍스트에는 검증 전 `[n]`이 그대로 들어 있다. 클라이언트는 `final`의 `answer`와 `citations`를 기준으로 렌더링한다. 모델이 근거 부족 토큰을 내면 그 토큰은 `token`으로 흘리지 않고 `final`의 `status=insufficient_context`로만 알린다. LLM 동시 호출 자리는 스트림이 끝나거나 클라이언트가 연결을 끊을 때 돌려준다.

#### 재호출하면

`/v1/query`와 같다.

---

## 데이터 모델

`app/schema/query_schema.py`의 `QueryRequest`, `QueryResponse`, `Citation`, `QueryMeta`, `TokenUsage`, `app/schema/chunk_schema.py`의 `Document`, `Chunk`, `app/schema/vector_schema.py`의 `IndexContract`. OpenAPI 문서는 서버의 `/docs`에서 볼 수 있다.
