# RAG QA 기능 정의서

---

## 서비스 개요

고정된 공개 문서셋을 근거로 질문에 답하고, 답에 출처를 붙이며, 근거가 없으면 답하지 않는 질의응답 서비스. 시스템은 오프라인 Ingest 경로(쓰기)와 온라인 Query 경로(읽기)로 나뉘고, 같은 저장소에 선정 실험과 Gold Set 기반 평가 도구를 함께 둔다.

범위 밖: 사용자 인증, 문서 업로드 API, 다중 턴 대화. 화면은 실시간 평가 대시보드 하나만 둔다.

---

## 기능 목록

| 기능 ID | 경로 | 기능 | 진입점 | 상태 |
|---|---|---|---|---|
| `corpus_fetch` | Ingest | manifest에 고정된 원문 다운로드와 해시 검증 | `make corpus` | 구현됨 |
| `eval_run` | Eval | test set 전체 채점과 Report 생성 | `make eval CONFIG=...` | 미구현 |
| `gold_draft` | Eval | 문서에서 Gold Set 초안 생성, 번역 묶음 생성, Gold 파일 검증 | `make gold-draft`, `make gold-translate`, `make gold-check` | 구현됨(dev, test) |
| `health` | Query | 프로세스 생존 확인, 벡터 DB 연결과 인덱스 계약 일치 확인 | `GET /health`, `GET /ready` | 구현됨 |
| `ingest` | Ingest | 정제, 청크, 임베딩, 인덱스 저장 | `make ingest` (`docker compose run --rm batch app.cli.ingest_cli`) | 구현됨 |
| `judge_agreement` | Eval | Judge 반복 일치율과 사람 라벨 대비 일치도 측정 | `make agreement` | 미구현 |
| `live_eval` | Eval | 실제 질의마다 정답 없이 잴 수 있는 지표를 누적하고 대시보드로 표시 | `GET /v1/metrics`, `GET /v1/metrics/stream`, `GET /dashboard` | 미구현 |
| `query` | Query | 검색, LLM 답변 생성, Citation 반환 또는 거절 | `POST /v1/query` (`make serve`) | 구현됨(dense 검색) |
| `query_stream` | Query | `query`의 SSE 스트리밍 버전 | `POST /v1/query/stream` | 구현됨 |
| `selection_run` | Eval | 선정 실험 실행 | `make profile`, `make closed-book`, `make closed-book-report`, `make db-bench` | 일부 구현 |

---

## 기능별 상세

### corpus_fetch: 원문 다운로드

**설명**: `data/corpus/candidates.json`의 원천 정의(GitHub 저장소, 고정 commit, 경로 접두사, 확장자)대로 원문을 받아 `data/corpus/raw/<이름>/`에 둔다. 처음 실행하면 파일별 sha256을 `data/corpus/manifests/<이름>.json`에 기록하고, 이후 실행은 manifest와 해시가 맞는 파일을 건너뛰며 다른 파일은 거부한다. 원천 정의가 바뀌면 manifest를 지우기 전까지 실패한다.

**입력과 결과**

| 입력 | 결과 |
|---|---|
| manifest 없음 | 트리 조회, 원문 다운로드, manifest 작성 |
| manifest 있음, 로컬 파일 정상 | 다운로드 0건 |
| 원격 내용이 manifest 해시와 다름 | `sha256 mismatch` 실패 |
| 원천 정의와 manifest 불일치 | 실패, manifest 삭제 안내 |
| 원문 디렉토리 밖을 가리키는 경로 | `unsafe path` 실패 |

**처리 흐름**: `corpus_cli fetch`에서 `CorpusFetcher.sync`로, `GitHubClient.list_tree`(manifest 없을 때만), `GitHubClient.download_file`, 해시 검증, 원자적 쓰기 순.

**구현 파일**

| 파일 | 층 | 역할 |
|---|---|---|
| `app/cli/corpus_cli.py` | cli | 명령 진입점 |
| `app/service/ingest/corpus_fetcher.py` | service | 다운로드, 해시 검증, manifest 작성 |
| `app/client/github_client.py` | client | 고정 commit의 트리 조회와 원문 다운로드 |
| `app/schema/corpus_schema.py` | schema | 원천 정의, manifest 모델 |
| `app/common/content_hasher.py` | common | sha256 계산 |

**테스트**

| 종류 | 파일 |
|---|---|
| 단위 | `tests/unit/test_corpus_fetch_corpus_fetcher.py` |

**제약과 미구현**: GitHub 원천만 지원한다. Docker 일회성 서비스 실행은 미구현.

### eval_run: 평가 실행

**설명**: 설정 파일 하나로 test set 전체를 `query_service`에 직접 넣고 지표를 계산해 Report를 만든다. 실행 환경(git hash, 모델 버전, 토크나이저, 프롬프트 해시, seed)을 함께 기록한다.

**처리 흐름**: `eval_cli`에서 `eval_service.run`으로, `gold_set_loader`, `query_service`, `retrieval_metric`, `refusal_metric`, `judge_metric`, `report_writer` 순.

**구현 파일**

| 파일 | 층 | 역할 |
|---|---|---|
| `app/cli/eval_cli.py` | cli | `run` 하위 명령 |
| `app/service/eval/eval_service.py` | service | 평가 파이프라인 조립, run_id 계산 |
| `app/service/eval/gold_set_loader.py` | service | dev, test set 로드와 검증 |
| `app/service/eval/retrieval_metric.py` | service | 근거 단위 Hit@k, MRR, 근거 재현율, 문서 단위 Recall@k. 구현됨 |
| `app/service/eval/refusal_metric.py` | service | 거절 정확도 |
| `app/service/eval/judge_metric.py` | service | Judge 기반 지표 |
| `app/service/eval/report_writer.py` | service | results.jsonl, summary.md |
| `app/client/llm_cache.py` | client | 요청 해시 기반 응답 캐시(`LlmCache`). 구현됨(LLM 선정 실험에서 사용) |
| `app/schema/gold_schema.py` | schema | Gold 문항 모델 |
| `app/schema/eval_schema.py` | schema | 문항별 결과, 요약 모델 |

**테스트**

| 종류 | 파일 |
|---|---|
| 단위 | `tests/unit/test_eval_run_retrieval_metric.py` |
| 단위 | `tests/unit/test_eval_run_refusal_metric.py` |
| 단위 | `tests/unit/test_eval_run_judge_metric.py` |
| 단위 | `tests/unit/test_eval_run_llm_cache.py` |
| 통합 | `tests/integ/test_eval_run.py` |

**제약과 미구현**: 지표 목록은 `research/gold_metric_selection.md`에서 확정. 결과는 `reports/<run_id>/`와 함께 평가 기록 저장소에 `source=gold`로 넣어 `live_eval`의 기준선으로 쓴다.

### gold_draft: Gold Set 초안 생성

**설명**: 확정된 Corpus에서 유형별(factual, multi_doc, summary, trap, unanswerable) 원문을 seed로 고정해 고르고, LLM 구조화 출력으로 질문, 정답, 근거 인용 초안을 만든다. 근거 인용은 원문과 공백 차이만 허용해 대조하고, 실패하면 1회 재시도 후 버린다. 초안은 `data/gold/drafts/<split>_draft.jsonl`에 쓰고, 검수를 거친 정본(`data/gold/<split>_set.jsonl`)은 건드리지 않는다. `gold-check`는 정본의 스키마, id 중복, 근거 인용의 원문 일치를 검사한다.

**입력과 결과**

| 입력 | 결과 |
|---|---|
| `make gold-draft SPLIT=dev` | 유형별 개수(factual 12, multi_doc 8, summary 5, trap 5, unanswerable 8)의 초안. 다시 실행하면 초안 파일만 덮어씀(LLM 출력은 매번 다를 수 있음) |
| `make gold-draft SPLIT=test` | factual 12, multi_doc 10(그중 추론 4), summary 6, trap 4, unanswerable 8의 초안과 `acceptance_criteria`, `rejection_criteria`. 표집 seed를 dev와 달리 하고, dev에서 쓴 문서를 뒤로 미루고, dev 근거 구절과 dev 질문을 프롬프트에 넣어 피하게 한다 |
| 근거 인용이 원문에 없음, dev 근거 구절과 60자 창을 공유, `acceptance_criteria`가 빔 | 피드백과 함께 재시도, 두 번째도 실패하면 그 문항을 버리고 수를 로그로 남김 |
| `make gold-translate SPLIT=dev` | 검수된 영어 정본의 질문을 한국어로 옮긴 초안. 근거와 정답은 원문 행 그대로, `translation_of`로 짝을 기록. 빠진 번역이 있으면 실패 |
| `make gold-check SPLIT=dev LANG_CODE=en\|ko` | 문제가 없으면 종료 코드 0, 있으면 문제 목록과 종료 코드 1. 번역 묶음은 원문 행과의 짝도 검사. test set은 모든 문항의 `acceptance_criteria`, dev 근거 구절과의 분리, 추론 문항 수(4 이상)도 검사 |

**구현 파일**

| 파일 | 층 | 역할 |
|---|---|---|
| `app/cli/eval_cli.py` | cli | `gold-draft`, `gold-check` 하위 명령 |
| `app/service/eval/gold_sampler.py` | service | 유형별 원문 표집, 내부 링크 해석, 목차 생성 |
| `app/service/eval/gold_drafter.py` | service | 초안 생성, 근거 대조, 재시도 |
| `app/service/eval/gold_translator.py` | service | 질문 번역 묶음 생성(8문항씩) |
| `app/service/eval/evidence_matcher.py` | service | 근거 인용 위치 찾기(검색 지표에서도 재사용) |
| `app/service/eval/retrieval_metric.py` | service | `shares_evidence`: 두 근거 구절이 60자 창을 공유하는지(dev와 test 분리 검사) |
| `app/schema/gold_schema.py` | schema | Gold 문항 모델, 답 있음과 근거의 일관성 검증 |
| `app/client/llm_client.py` | client | JSON Schema 구조화 출력 |

**테스트**

| 종류 | 파일 |
|---|---|
| 단위 | `tests/unit/test_gold_draft_gold_sampler.py` |
| 단위 | `tests/unit/test_gold_draft_gold_drafter.py` |
| 단위 | `tests/unit/test_gold_draft_gold_translator.py` |

**제약과 미구현**: 행 스키마는 `data/gold/README.md`, 구축 기록은 `research/dev_set_construction.md`(dev)와 `research/gold_metric_selection.md`(test).

### health: 상태 확인

**설명**: `/health`는 프로세스가 살아 있으면 200을 돌려준다. `/ready`는 벡터 DB에 연결되고 인덱스 계약이 서버 설정과 일치할 때만 200, 아니면 503을 돌려준다. compose healthcheck는 `/ready`를 쓴다.

**구현 파일**

| 파일 | 층 | 역할 |
|---|---|---|
| `app/api/health_router.py` | api | 두 엔드포인트 |
| `app/repository/qdrant_chunk_repository.py` | repository | `read_contract`(컬렉션 메타데이터 조회, 없으면 None) |

**테스트**

| 종류 | 파일 |
|---|---|
| 통합 | `tests/integ/test_query.py`(`/ready` 계약 일치와 벡터 DB 장애) |

**제약과 미구현**: 없음.

### ingest: 색인

**설명**: 원문을 정제, 청크, 임베딩해 벡터 DB에 upsert하고 컬렉션 메타데이터에 인덱스 계약(임베딩 모델, 토크나이저, Chunk 설정 해시)을 기록한다. 같은 입력으로 다시 돌리면 같은 상태로 수렴한다.

**처리 흐름**: `ingest_cli`에서 `ingest_service.run`으로, `document_loader`, `text_cleaner`, `chunk_splitter`(`embedding_client.token_count`로 길이 측정), 청크에 문서 제목과 원문 URL(고정 commit) 부착, `embedding_client`, `sparse_encoder`(`text_tokenizer`로 BM25 토큰화), `ensure_collection`, `upsert`, `delete_except`(원문에서 사라진 청크 삭제) 순.

**재실행하면**: 컬렉션 이름이 인덱스 계약의 해시라 같은 설정이면 같은 컬렉션에 upsert하고, 이번 실행에 없는 청크를 지워 같은 상태로 수렴한다. 설정을 바꾸면 새 컬렉션이 생기고 기존 컬렉션은 남는다.

**구현 파일**

| 파일 | 층 | 역할 |
|---|---|---|
| `app/cli/ingest_cli.py` | cli | 명령 진입점. 설정에서 확정 구성을 조립 |
| `app/service/ingest/ingest_service.py` | service | 파이프라인 조립(`IngestService`) |
| `app/service/ingest/document_loader.py` | service | manifest 순서로 원문을 읽어 정제한 Document로 만듦. 구현됨 |
| `app/service/ingest/text_cleaner.py` | service | front matter, HTML 주석, HTML 태그 제거. Markdown 링크와 `<name>` 같은 자리표시자는 유지(근거 인용과 대조하기 위해). 구현됨 |
| `app/service/ingest/chunk_splitter.py` | service | `ChunkSplitter`: 임베딩 토큰 수 기준 고정 길이, 슬라이딩 윈도우(겹침 50%), 재귀(문단, 줄, 문장, 단어), 문서 구조(Markdown 제목 단위), 시맨틱(이웃 문장 임베딩 거리 95 백분위) 분할과 겹침. `FixedLengthSplitter`: 앞선 선정 실험이 쓴 문자 수 고정 분할 |
| `app/common/text_tokenizer.py` | common | BM25 단어 토큰화(Query와 공유). 선정 설정 `word`. 비교용 kiwi, okt, kkma 모드는 `korean` 의존성 그룹이 있을 때만 import. 구현됨 |
| `app/service/ingest/sparse_encoder.py` | service | `SparseEncoder`: BM25 sparse 벡터(문서 쪽 k1, b 가중, crc32 해시, 질의는 단어마다 1). Query와 공유. 구현됨 |
| `app/service/ingest/sentence_embedder.py` | service | 시맨틱 분할용 문장 임베딩. 같은 문장은 한 번만 임베딩 |
| `app/client/embedding_client.py` | client | 배치 임베딩, 잘림 없는 토큰 수와 토큰 위치(Query와 공유). 로컬 fastembed, Qwen3-Embedding-0.6B(확정) |
| `app/repository/qdrant_chunk_repository.py` | repository | `ensure_collection`, `upsert`, `delete_except`, 검색(dense, 점수를 함께 주는 dense, 청크를 돌려주는 dense, sparse, RRF 결합). 선정된 DB |
| `app/schema/chunk_schema.py` | schema | Document, Chunk 모델. chunk_id는 (doc_id, text)의 sha256 |
| `app/schema/vector_schema.py` | schema | sparse 벡터, 인덱스 계약과 계약 해시로 만든 컬렉션 이름 |
| `app/common/settings.py` | common | 확정 구성 값과 인덱스 계약 생성(`index_contract`, Ingest와 Query 공유) |

**테스트**

| 종류 | 파일 |
|---|---|
| 단위 | `tests/unit/test_ingest_chunk_splitter.py`(정제, 문자 수 분할, 토큰 기준 분할 5방식) |
| 단위 | `tests/unit/test_ingest_text_tokenizer.py` |
| 단위 | `tests/unit/test_ingest_sparse_encoder.py` |
| 단위 | `tests/unit/test_ingest_sentence_embedder.py` |
| 통합 | `tests/integ/test_ingest.py`(재실행 수렴, 계약 기록, 사라진 문서의 청크 삭제) |

**제약과 미구현**: 시맨틱 분할은 Ingest에서 받지 않는다. 길이 단위(Qwen3 토큰)와 BM25 토큰화(`word`)는 토크나이저 선정에서 확정. 분할은 Chunking 선정에서 `structure-512-77`로 확정. 모델은 Embedding 교차 확인에서 Qwen3-Embedding-0.6B로 확정.

### judge_agreement: Judge 신뢰성 측정

**설명**: 같은 입력으로 Judge를 3회 돌린 판정 일치율과, 사람 라벨(`data/gold/human_labels.jsonl`) 대비 일치율과 Cohen's kappa를 계산한다. Judge 모델 선정 근거로도 쓴다.

**구현 파일**

| 파일 | 층 | 역할 |
|---|---|---|
| `app/cli/eval_cli.py` | cli | `agreement` 하위 명령 |
| `app/service/eval/agreement_service.py` | service | 반복 실행과 비교 조립 |
| `app/service/eval/agreement_calculator.py` | service | 일치율, kappa 계산 |

**테스트**

| 종류 | 파일 |
|---|---|
| 단위 | `tests/unit/test_judge_agreement_agreement_calculator.py` |

**제약과 미구현**: 전부 미구현.

### live_eval: 실시간 누적 평가

**설명**: `query`, `query_stream` 응답마다 기록을 남기고, 백그라운드 Judge가 뒤따라 채점하고, 집계기가 누적 평균, 95% 구간, 최근 50건 이동 창을 계산해 API와 대시보드로 보낸다. 같은 `config_id`의 Gold Set 평가값을 기준선으로 겹친다. 지표 정의는 `research/gold_metric_selection.md`.

**처리 흐름**: `query_service` 응답 뒤 `eval_recorder`가 저장, `judge_worker`가 채점 안 된 기록을 꺼내 `judge_metric`으로 판정, `metric_aggregator`가 집계, `metrics_router`가 응답.

**구현 파일(예정)**

| 파일 | 층 | 역할 |
|---|---|---|
| `app/api/metrics_router.py` | api | `/v1/metrics`, `/v1/metrics/stream`, `/dashboard` |
| `app/service/eval/eval_recorder.py` | service | 질의 기록 저장. 실패해도 응답에 영향 없음 |
| `app/service/eval/judge_worker.py` | service | 큐, 샘플링, 예산 상한, 재시작 시 미채점 기록 재처리 |
| `app/service/eval/metric_aggregator.py` | service | 누적 평균, Wilson 구간, 이동 창 |
| `app/repository/eval_record_repository.py` | repository | SQLite 기록과 판정 upsert |

**제약과 미구현**: 전부 미구현. Judge 신뢰성 기준을 통과한 항목만 대시보드에 올린다.

### query: 질의응답

**설명**: 질문을 받아 인덱스를 검색하고, 검색한 근거만으로 답하며 `[n]` 인용을 출처 정보로 바꿔 돌려준다. 근거가 부족하면 `insufficient_context`를 돌려준다. 저장소에 쓰지 않는다.

**입력과 결과**

| 입력 | 결과 |
|---|---|
| 문서에 근거가 있는 질문 | `status=answered`, 답변, 인용 목록 |
| 검색 최고 점수가 임계값 미만인 질문 | LLM 호출 없이 `status=insufficient_context` |
| 근거는 검색됐지만 답이 없는 질문 | 모델의 근거 부족 토큰을 감지해 `status=insufficient_context` |
| 빈 질문, 1000자를 넘은 질문, 범위 밖 `top_k` | 422 |
| `API_KEY`가 설정됐는데 `X-API-Key`가 없거나 틀림 | 401 |
| LLM 동시 호출 상한 대기 한도 초과 | 503, `Retry-After` |
| LLM 호출 실패, 타임아웃 | 502, 504 |
| 벡터 DB 연결 실패 | 503 |
| 색인과 다른 임베딩 모델, 토크나이저, Chunk 설정으로 기동 | 기동 실패 |

**처리 흐름**: `query_router`에서 `query_service.answer`로, `chunk_retriever`(`embedding_client`를 스레드에서 호출, `search_dense_chunks`), `evidence_checker`(점수 임계값), `prompt_builder`, `llm_gate`(동시 호출 상한), `llm_client`, `evidence_checker`(근거 부족 토큰), `citation_parser` 순.

**구현 파일**

| 파일 | 층 | 역할 |
|---|---|---|
| `app/main.py` | api | lifespan에서 클라이언트 조립, 인덱스 계약 검증 |
| `app/api/query_router.py` | api | 요청 검증, 응답 변환 |
| `app/api/request_middleware.py` | api | 요청 ID, 처리 시간 로그 |
| `app/api/api_key_guard.py` | api | `X-API-Key` 검사 |
| `app/api/error_mapper.py` | api | 예외를 HTTP 상태로 변환 |
| `app/api/query_runtime.py` | api | 요청 사이에 공유하는 객체 묶음(`QueryRuntime`)과 라우터 의존성 |
| `app/service/query/query_service.py` | service | 파이프라인 조립 |
| `app/service/query/chunk_retriever.py` | service | dense 검색 |
| `app/service/query/llm_gate.py` | service | LLM 동시 호출 상한과 대기 한도 |
| `app/service/query/evidence_checker.py` | service | 점수 임계값과 근거 부족 토큰 판정 |
| `app/service/query/prompt_builder.py` | service | 번호 매긴 근거와 지시문 조립 |
| `app/service/query/citation_parser.py` | service | `[n]` 추출, 존재하지 않는 번호 제거 |
| `app/repository/qdrant_chunk_repository.py` | repository | `search_dense_chunks`. 저장소 오류를 `VectorStoreError`로 변환 |
| `app/client/llm_client.py` | client | OpenAI 호환 채팅 호출. seed, temperature는 None이면 보내지 않음. 타임아웃과 실패를 `LlmTimeoutError`, `LlmFailureError`로 변환 |
| `app/common/upstream_error.py` | common | 외부 의존 실패 예외(`UpstreamError` 하위 4종) |
| `app/client/embedding_client.py` | client | 질의 벡터화 |
| `app/schema/query_schema.py` | schema | `QueryRequest`, `QueryResponse`, `Citation`, `QueryMeta`, `RetrievedChunk`, `ParsedAnswer` |

**테스트**

| 종류 | 파일 |
|---|---|
| 단위 | `tests/unit/test_query_citation_parser.py` |
| 단위 | `tests/unit/test_query_evidence_checker.py` |
| 단위 | `tests/unit/test_query_prompt_builder.py` |
| 단위 | `tests/unit/test_query_query_service.py` |
| 단위 | `tests/unit/test_query_llm_gate.py` |
| 통합 | `tests/integ/test_query.py`(앱 전체에 메모리 저장소, 임베딩, 대체 LLM. 응답, 두 단계 거절, 401, 422, 요청 ID, 502, 503, 504, `/ready`) |

**제약과 미구현**: 검색은 dense만 구현했다. hybrid(dense와 BM25를 RRF로 결합)는 Part C에서 설정으로 켠다. 색인에는 sparse 벡터가 이미 들어 있어 다시 색인할 필요가 없다. 임베딩은 로컬 모델이라 호출 타임아웃을 두지 않는다.

### query_stream: 스트리밍 질의응답

**설명**: `query`와 같은 파이프라인을 쓰고 생성 토큰을 `token` 이벤트로 흘린 뒤, 검증한 인용 목록과 메타(첫 토큰 지연 포함)를 `final` 이벤트로 보낸다. 검색 단계에서 거절되면 `token` 없이 `final`만 보낸다. 첫 이벤트 전 실패는 HTTP 상태로, 그 뒤 실패는 `error` 이벤트로 알린다.

**구현 파일**

| 파일 | 층 | 역할 |
|---|---|---|
| `app/api/query_router.py` | api | SSE 응답. 첫 이벤트를 받은 뒤 응답 시작, 끊기면 생성기를 닫음 |
| `app/api/error_mapper.py` | api | `describe`: 스트림 `error` 이벤트의 상태와 메시지 |
| `app/service/query/query_service.py` | service | `answer_stream`: 근거 부족 토큰이 새지 않게 앞부분을 보류하며 흘리고 마지막에 `QueryResponse` |
| `app/client/llm_client.py` | client | `stream`: 텍스트 조각(`LlmDelta`)과 마지막 사용량(`LlmCompletion`) |

**테스트**

| 종류 | 파일 |
|---|---|
| 단위 | `tests/unit/test_query_query_service.py`(스트림 토큰과 final 일치, 근거 부족 토큰 보류) |
| 통합 | `tests/integ/test_query.py`(token 뒤 final, JSON 응답과 같은 인용, 점수 거절 시 final만, 도중 실패 error 이벤트, 첫 이벤트 전 실패 503) |

**제약과 미구현**: 스트리밍 중 흘린 텍스트에는 검증 전 `[n]`이 그대로 있다. 존재하지 않는 번호는 `final`의 답변과 인용 목록에서만 빠진다. 모델이 근거 부족 토큰 앞에 다른 말을 붙이면 그 말은 `token`으로 나간다(최종 상태는 `final`이 정한다). LLM 동시 호출 자리는 스트림이 끝날 때까지 잡혀 있다.

### selection_run: 선정 실험

**설명**: 데이터셋, 데이터베이스, Embedding, 토크나이저, Chunking, LLM 선정을 위한 실험을 설정 파일 단위로 실행하고 결과 표를 출력한다. Ingest, Query 모듈을 설정만 바꿔 재사용하며 선정에는 dev set만 쓴다. 해석과 결정은 `research/<주제>.md`에 기록한다.

| 실험 | 측정 |
|---|---|
| `profile` | 후보 Corpus별 규모, 구조, 파싱 난이도, 함정 요소 통계. 구현됨 |
| `closed_book` | 후보 Corpus별 근거 없는 질의를 seed별로 반복해 답변 수집. 구현됨 |
| `closed_book_report` | 블라인드 채점 결과를 답변에 붙여 후보별 오답, 모름, 다수결 판정 집계. 구현됨 |
| `tokenizer` | 길이 단위별 임베딩 토큰 대비 비율 분포, 문자 수 상한의 목표 초과 비율과 채움률, BM25 토크나이저 7종(규칙 4종, Kiwi, Okt, Kkma)별 sparse 단독 Hit@5, MRR, 처리 시간, 어휘와 해시 충돌. 구현됨(`make tok-bench`, `batch-korean` 이미지) |
| `chunking` | 분할 방식 5종(크기 512, 겹침 15%, 슬라이딩은 50%)을 먼저 비교하고 한 방식(`--method`, 기본 `structure`)만 크기(256, 512, 1024)와 겹침(0%, 15%, 슬라이딩은 25%, 50%)을 바꿔 Hit@5, MRR, 근거 보존율, 근거 보존@5와 @10, 청크 수, 질의당 근거 토큰 수, 분할 시간 측정. 구현됨(`make chunk-bench`) |
| `database` | 후보 DB별 기능 검사 6종, 적재 시간, 질의 지연 p50과 p95, 메모리 사용량, numpy 전수 비교 대비 ANN 재현율. 구현됨(`make db-bench`) |
| `embedding` | 임베딩 후보별 근거 단위 Hit@5, Hit@10, MRR, 근거 재현율, 문서 단위 Recall@5(영어, 한국어 질의), bootstrap 신뢰구간, 색인 시간, 질의 임베딩 지연. 구현됨(`make embed-bench`). 교차 확인은 `embedding_crosscheck` |
| `embedding_crosscheck` | 확정 Chunking 청크로 Qwen3와 e5를 다시 색인해 Hit@5, MRR, 근거 보존@5와 @10, e5 잘림 청크 수 측정과 사전 규칙 판정. 구현됨(`make embed-check`) |
| `refusal_threshold` | dev set 답 있음/답 없음 문항의 dense 최고 점수 분포와 임계값별 오거절, 미거절 비율, 언어별 오거절 상한(5%) 판정. 구현됨(`make refusal-calib`) |
| `llm` | 생성 후보별 인용 형식 준수율, 지운 인용 비율, 답 있음 오거절, 답 없음 거절, 문항당 비용과 지연, 사전 규칙 판정. 응답 캐시로 재실행 비용 0. 구현됨(`make llm-bench`) |

**구현 파일**

| 파일 | 층 | 역할 |
|---|---|---|
| `app/cli/corpus_cli.py` | cli | `profile` 명령 |
| `app/cli/selection_cli.py` | cli | `closed-book` 명령 |
| `app/service/eval/corpus_profiler.py` | service | Corpus 통계 |
| `app/service/eval/closed_book_prober.py` | service | closed-book 질의 |
| `app/service/eval/closed_book_reporter.py` | service | 채점 집계, 다수결 판정 |
| `app/client/llm_client.py` | client | OpenAI 호환 채팅 호출 |
| `app/schema/selection_schema.py` | schema | closed-book 문항과 답변 모델 |
| `app/cli/database_selection_cli.py` | cli | DB 후보 접속, 청크와 임시 벡터 준비, 결과 저장 |
| `app/cli/embedding_selection_cli.py` | cli | 임베딩 후보 정의(접두어, 최대 입력), 결과와 짝지은 차이 저장 |
| `app/service/eval/embedding_benchmark.py` | service | 모델별 색인(`index`), Qdrant 정확 검색(`search`), 지표 요약. Chunking 실험도 `index`, `search`를 쓴다 |
| `app/service/eval/retrieval_metric.py` | service | 근거 단위 Hit@k, MRR, 근거 재현율, 문서 Recall(60자 창 근거 판정), bootstrap 구간과 짝지은 차이 |
| `app/cli/tokenizer_selection_cli.py` | cli | 길이 단위와 BM25 후보 정의, 결과와 짝지은 차이 저장 |
| `app/service/eval/tokenizer_benchmark.py` | service | 단위별 길이 비율, 문자 상한 검사, BM25 sparse 단독 검색 측정 |
| `app/cli/chunking_selection_cli.py` | cli | 분할 후보 정의, 시맨틱 분할용 문장 임베딩 캐시, 두 단계 실행(방식, 크기와 겹침), 결과와 판정 저장 |
| `app/service/eval/chunking_benchmark.py` | service | 설정별 색인과 정확 검색, 근거 보존율, 근거 보존@k(`evidence_covered`), 질의당 근거 토큰 수, 사전 규칙 판정(`pick_best`) |
| `app/cli/embedding_crosscheck_cli.py` | cli | 확정 Chunking(`structure-512-77`)으로 Embedding 상위 두 모델(Qwen3, e5) 재측정, 결과와 판정 저장 |
| `app/service/eval/embedding_crosscheck.py` | service | 모델 최대 입력을 넘는 청크 수(`truncated_chunks`), 교차 확인 사전 규칙 판정(`judge`: Hit@5 짝지은 차이, 근거 보존@5, 비용) |
| `app/cli/refusal_calibration_cli.py` | cli | 확정 구성으로 색인, dev set 전 문항의 dense 최고 점수 측정, 결과와 판정 저장 |
| `app/service/eval/refusal_calibrator.py` | service | 임계값 후보별 언어별 오거절, 거절 비율과 사전 규칙 판정(`pick_threshold`) |
| `app/cli/llm_selection_cli.py` | cli | 확정 검색 구성으로 dev set 근거 검색, 후보별 생성, 결과와 판정 저장 |
| `app/service/eval/llm_benchmark.py` | service | 두 단계 거절(점수, 근거 부족 토큰), 인용 파싱, 응답 캐시를 거친 후보별 생성(`LlmBenchmark`), 요약(`summarize_llm`), 판정(`pick_llm`) |
| `app/service/eval/database_benchmark.py` | service | 기능 검사, 적재, 지연, ANN 재현율 측정 |
| `app/service/eval/vector_projector.py` | service | 무작위 투영으로 차원 변경, numpy 전수 비교 |
| `app/service/eval/term_hasher.py` | service | 기능 검사용 임시 sparse 인코더 |
| `app/repository/pgvector_chunk_repository.py` | repository | 후보 구현(기각) |
| `app/repository/chroma_chunk_repository.py` | repository | 후보 구현(기각). 서버가 sparse 인덱스를 거부하면 dense만으로 만들고 사유 기록 |

**테스트**

| 종류 | 파일 |
|---|---|
| 단위 | `tests/unit/test_selection_run_corpus_profiler.py` |
| 단위 | `tests/unit/test_selection_run_closed_book_prober.py` |
| 단위 | `tests/unit/test_selection_run_closed_book_reporter.py` |
| 단위 | `tests/unit/test_selection_run_vector_projector.py` |
| 단위 | `tests/unit/test_selection_run_retrieval_metric.py` |
| 단위 | `tests/unit/test_selection_run_tokenizer_benchmark.py` |
| 단위 | `tests/unit/test_selection_run_chunking_benchmark.py`, `tests/unit/test_selection_run_embedding_crosscheck.py`, `tests/unit/test_selection_run_refusal_calibrator.py`, `tests/unit/test_selection_run_llm_benchmark.py` |
| 통합 | `tests/integ/test_selection_run.py`(Chunking 선정, Embedding 교차 확인, 거절 임계값 보정, LLM 선정 파이프라인: 분할, 색인, 검색, 생성, 캐시 재사용, 지표, 잘림 수, 점수, 판정. LLM은 대체 객체. 벡터 DB와 임베딩 모델은 메모리 대체 객체) |

**제약과 미구현**: 데이터셋, 데이터베이스, Embedding, 토크나이저, Chunking, Embedding 교차 확인, 거절 임계값 보정, LLM 선정 외 실험은 미구현. DB 저장소 3종은 실제 DB가 필요해 단위 테스트 대신 `make db-bench`의 기능 검사로 검증한다. 기각된 후보 구현은 실험 재현을 위해 남긴다.

---

## 공통 모듈

| 파일 | 역할 |
|---|---|
| `app/common/logger.py` | structlog 로거. `LOG_FORMAT`으로 콘솔과 JSON 전환 |
| `app/common/settings.py` | pydantic-settings 환경변수 로딩. 키 누락 시 기동 실패 |
| `app/common/content_hasher.py` | 파일, 텍스트, 설정의 sha256 |
| `app/common/text_tokenizer.py` | BM25 단어 토큰화. 선정 설정 `word`. Ingest와 Query가 같은 설정을 씀. 형태소 분석기 모드는 실험 전용 |
