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
| Query | 읽기, 온라인 | 질문, 검색, LLM 답변 생성, Citation 반환 | FastAPI `POST /v1/query`, `POST /v1/query/stream` | 벡터 DB 읽기 전용. 응답 뒤 평가 기록 저장소(`evaldb`)에 쓰기 |
| 실시간 평가 | 온라인 | 응답 뒤 기록, 백그라운드 Judge, 누적 집계 | `GET /v1/metrics`, `GET /v1/metrics/stream`, `GET /dashboard` | 평가 기록 저장소 읽기, 쓰기 |

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
| `GET` | `/v1/metrics` | 실시간 누적 지표 | 구현됨 |
| `GET` | `/v1/metrics/stream` | 실시간 누적 지표 SSE | 구현됨 |
| `GET` | `/dashboard` | 실시간 평가 대시보드(정적 HTML, 인증 없음. 데이터는 화면이 `/v1/metrics/stream`에서 받음) | 구현됨 |

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
| `meta.retrieval_scores` | float[] | 근거로 쓴 청크의 검색 방식 점수(내림차순). dense면 코사인 유사도, bm25면 BM25 내적, rrf와 cc면 융합 점수. 기본(routed)은 한국어 질의면 코사인 유사도, 영어 질의면 CC 점수 |
| `meta.top_dense_score` | float \| null | 거절 판정에 쓴 dense 최고 점수. 검색 방식과 관계없이 dense로 판정한다. 검색 결과가 없으면 null |
| `meta.dropped_citations` | int | 존재하지 않는 번호라 버린 인용 수 |
| `meta.latency_ms` | int | 서버 처리 시간 |
| `meta.retrieval_ms` | int \| null | 질의 임베딩과 벡터 검색에 걸린 시간. `latency_ms`와 `first_token_ms`에 포함된다 |
| `meta.usage` | object | `input_tokens`, `output_tokens`. 검색 단계에서 거절하면 0 |
| `meta.first_token_ms` | int \| null | 스트리밍 응답에서 첫 `token` 이벤트까지 걸린 시간(검색 포함). 비스트리밍이나 토큰이 없으면 null |

#### 재호출하면

벡터 DB와 인덱스는 바뀌지 않는다. 같은 질문과 같은 인덱스면 검색 결과와 검색 단계 거절 여부는 같다. 실시간 평가가 켜져 있고 `top_k`가 기본값(생략 또는 5)이면 응답을 보낸 뒤 평가 기록 저장소에 기록 하나를 남긴다. 기록 키는 `live:<X-Request-ID>`라, 같은 `X-Request-ID`로 다시 보내면 같은 행을 덮어쓰고 행이 늘지 않는다. 기록이나 채점에 실패해도 응답은 그대로다. 생성은 temperature 0이지만 생성 모델(claude-haiku-5-5)이 seed를 받지 않아, 모델 제공자 측 비결정성 때문에 문구가 달라질 수 있다.

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

`/v1/query`와 같다. 평가 기록은 `final` 이벤트까지 보낸 응답만 스트림이 끝난 뒤 남긴다.

### GET /v1/metrics

실제 질의(`source=live`)의 최근 기록(기본 2,000개)을 지표별로 집계한다. 인증은 `/v1/query`와 같다. 실시간 평가가 꺼져 있으면(평가 저장소 비밀번호나 Judge 엔드포인트가 없거나, 저장소 연결 실패) 503.

| 필드 | 타입 | 설명 |
|---|---|---|
| `config_id` | string | 파이프라인 구성 해시. Gold Set 평가와 같은 함수로 계산 |
| `records`, `answered`, `judged` | int | 기록 수, 답한 수, Judge 판정이 있는 수 |
| `judge_spent_krw`, `judge_limit_krw`, `judge_exhausted` | float, float, bool | 실시간 채점 누적 비용, 상한, 상한 도달 여부. 도달하면 채점만 멈춘다 |
| `baseline_run` | string \| null | 기준선으로 쓴 Gold Set 실행(같은 `config_id`, 변형 없음) |
| `metrics[].key`, `label`, `unit` | string | 지표 키, 영문 지표명, 단위(`rate`, `ms`, `krw`, `score`) |
| `metrics[].description` | string | 지표의 뜻(한국어 한 줄). 화면은 카드 제목 바로 아래에 보여준다 |
| `metrics[].group` | string | 화면 묶음. `retrieval`(검색), `generation`(생성), `ops`(운영) |
| `metrics[].reference` | bool | 검증 조건을 통과하지 못한 참고값 |
| `metrics[].baseline` | float \| null | 같은 지표의 Gold Set 전체 평균 |
| `metrics[].verdict` | string \| null | 기준선 판정. `within`(기준선이 누적 95% 구간 안), `above`(구간이 기준선보다 위), `below`(아래), `few`(표본 10개 미만이라 판정 보류). 기준선이나 값이 없으면 null |
| `metrics[].points[]` | object | `n`(표본 수), `cum`(누적 평균), `low`, `high`(95% 구간. 비율은 Wilson, 나머지는 정규 근사이고 0~1 점수는 [0, 1]로 자른다), `window`(최근 50개 평균). 200개를 넘으면 고르게 솎고 마지막 지점은 남긴다 |
| `recent[]` | object | 최근 100건, 최신이 먼저. `request_id`, `recorded_at`(저장 시각, UTC), `status`, `refusal_stage`, `top_score`, `latency_ms`, `first_token_ms`, `cost_krw`, `judge`(`judged`, `failed`, `pending` 채점 대기, `skipped` 거절이나 표본 밖이나 예산 소진), `unsupported_claim`, `citation_precision`. 질문과 답 원문은 넣지 않는다 |
| `gold[]` | object | 대시보드 기준선 실행(`baseline_run`)의 언어별 요약. 평가 Report `summary.json`의 `languages`와 같은 형식(`language`, `items`, `retrieval`의 Recall@k, MRR, nDCG와 95% 구간, `unanswerable_refusal`, `answerable_false_refusal`, `judge.accuracy`, `judge.citation_precision`, `ttft_ms`, `latency_ms`, `cost_krw_per_item` 등). 기준선이 없으면 빈 목록. 서버가 처음 계산한 뒤 재사용 |

지표(`group`, 지표명): `refusal_retrieval` Retrieval Refusal Rate(`retrieval`, 전체 질의 중 검색 단계 거절 비율), `near_threshold` Near-Threshold Rate(`retrieval`, 검색 최고 점수가 임계값 ±0.05 안인 비율), `refusal_generation` Generation Refusal Rate(`generation`, 검색 단계를 통과한 질의 중 LLM이 `INSUFFICIENT_CONTEXT`로 거절한 비율), `unsupported_claim` No Unsupported Claim(`generation`, 참고값), `citation_precision` Citation Precision(`generation`, 참고값), `latency_ms` Latency(`ops`, 답한 질의), `ttft_ms` TTFT(`ops`, 답한 스트리밍 질의), `cost_krw` Cost per Query(`ops`).

#### 재호출하면

읽기 전용이다. 새 기록이나 판정이 없으면 같은 값이 나온다.

### GET /v1/metrics/stream

연결 직후 `snapshot` 이벤트(`/v1/metrics`와 같은 본문)를 한 번 보내고, 기록이나 판정이 늘 때마다 새 `snapshot`을 보낸다. 변경이 없으면 15초마다 `: keepalive` 주석 줄을 보낸다. 인증과 503은 `/v1/metrics`와 같다.

#### 재호출하면

읽기 전용이다. 연결마다 독립이고, 끊으면 서버 쪽 루프도 끝난다.

---

## 데이터 모델

`app/schema/query_schema.py`의 `QueryRequest`, `QueryResponse`, `Citation`, `QueryMeta`, `TokenUsage`, `app/schema/chunk_schema.py`의 `Document`, `Chunk`, `app/schema/vector_schema.py`의 `IndexContract`. OpenAPI 문서는 서버의 `/docs`에서 볼 수 있다.
