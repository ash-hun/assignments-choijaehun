# RAG QA 기능 정의서

| 항목 | 값 |
|---|---|
| Last Updated | 2026-11-07 |

---

## 서비스 개요

고정된 공개 문서셋을 근거로 질문에 답하고, 답에 출처를 붙이며, 근거가 없으면 답하지 않는 질의응답 서비스. 시스템은 오프라인 Ingest 경로(쓰기)와 온라인 Query 경로(읽기)로 나뉘고, 같은 저장소에 선정 실험과 Gold Set 기반 평가 도구를 함께 둔다.

범위 밖: 사용자 인증, 문서 업로드 API, 다중 턴 대화, 웹 화면.

---

## 기능 목록

| 기능 ID | 경로 | 기능 | 진입점 | 상태 |
|---|---|---|---|---|
| `corpus_fetch` | Ingest | manifest에 고정된 원문 다운로드와 해시 검증 | `make corpus` | 구현됨 |
| `eval_run` | Eval | test set 전체 채점과 Report 생성 | `make eval CONFIG=...` | 미구현 |
| `gold_draft` | Eval | 문서에서 Gold Set 초안 생성, 번역 묶음 생성, Gold 파일 검증 | `make gold-draft`, `make gold-translate`, `make gold-check` | 구현됨(dev) |
| `health` | Query | 프로세스 생존 확인, 벡터 DB 연결과 인덱스 계약 일치 확인 | `GET /health`, `GET /ready` | 미구현 |
| `ingest` | Ingest | 정제, 청크, 임베딩, 인덱스 저장 | `make ingest` (`docker compose run --rm batch app.cli.ingest_cli`) | 일부 구현(로드, 정제, 고정 길이 분할, Qdrant 저장소) |
| `judge_agreement` | Eval | Judge 반복 일치율과 사람 라벨 대비 일치도 측정 | `make agreement` | 미구현 |
| `query` | Query | 검색, LLM 답변 생성, Citation 반환 또는 거절 | `POST /v1/query` | 미구현 |
| `query_stream` | Query | `query`의 SSE 스트리밍 버전 | `POST /v1/query/stream` | 미구현 |
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
| `app/client/llm_cache.py` | client | 요청 해시 기반 응답 캐시 |
| `app/schema/gold_schema.py` | schema | Gold 문항 모델 |
| `app/schema/eval_schema.py` | schema | 문항별 결과, 요약 모델 |

**테스트**

| 종류 | 파일 |
|---|---|
| 단위 | `tests/unit/test_eval_run_retrieval_metric.py` |
| 단위 | `tests/unit/test_eval_run_refusal_metric.py` |
| 단위 | `tests/unit/test_eval_run_judge_metric.py` |
| 통합 | `tests/integ/test_eval_run.py` |

**제약과 미구현**: 지표 목록은 Gold Set 및 Metric 선정 실험 후 확정.

### gold_draft: Gold Set 초안 생성

**설명**: 확정된 Corpus에서 유형별(factual, multi_doc, summary, trap, unanswerable) 원문을 seed로 고정해 고르고, LLM 구조화 출력으로 질문, 정답, 근거 인용 초안을 만든다. 근거 인용은 원문과 공백 차이만 허용해 대조하고, 실패하면 1회 재시도 후 버린다. 초안은 `data/gold/drafts/<split>_draft.jsonl`에 쓰고, 검수를 거친 정본(`data/gold/<split>_set.jsonl`)은 건드리지 않는다. `gold-check`는 정본의 스키마, id 중복, 근거 인용의 원문 일치를 검사한다.

**입력과 결과**

| 입력 | 결과 |
|---|---|
| `make gold-draft SPLIT=dev` | 유형별 개수(factual 12, multi_doc 8, summary 5, trap 5, unanswerable 8)의 초안. 다시 실행하면 초안 파일만 덮어씀(LLM 출력은 매번 다를 수 있음) |
| 근거 인용이 원문에 없음 | 피드백과 함께 재시도, 두 번째도 실패하면 그 문항을 버리고 수를 로그로 남김 |
| `make gold-translate SPLIT=dev` | 검수된 영어 정본의 질문을 한국어로 옮긴 초안. 근거와 정답은 원문 행 그대로, `translation_of`로 짝을 기록. 빠진 번역이 있으면 실패 |
| `make gold-check SPLIT=dev LANG_CODE=en\|ko` | 문제가 없으면 종료 코드 0, 있으면 문제 목록과 종료 코드 1. 번역 묶음은 원문 행과의 짝도 검사 |

**구현 파일**

| 파일 | 층 | 역할 |
|---|---|---|
| `app/cli/eval_cli.py` | cli | `gold-draft`, `gold-check` 하위 명령 |
| `app/service/eval/gold_sampler.py` | service | 유형별 원문 표집, 내부 링크 해석, 목차 생성 |
| `app/service/eval/gold_drafter.py` | service | 초안 생성, 근거 대조, 재시도 |
| `app/service/eval/gold_translator.py` | service | 질문 번역 묶음 생성(8문항씩) |
| `app/service/eval/evidence_matcher.py` | service | 근거 인용 위치 찾기(검색 지표에서도 재사용) |
| `app/schema/gold_schema.py` | schema | Gold 문항 모델, 답 있음과 근거의 일관성 검증 |
| `app/client/llm_client.py` | client | JSON Schema 구조화 출력 |

**테스트**

| 종류 | 파일 |
|---|---|
| 단위 | `tests/unit/test_gold_draft_gold_sampler.py` |
| 단위 | `tests/unit/test_gold_draft_gold_drafter.py` |
| 단위 | `tests/unit/test_gold_draft_gold_translator.py` |

**제약과 미구현**: test split 계획(SPLIT_PLANS)은 미정의. 행 스키마는 `data/gold/README.md`, 구축 기록은 `research/dev_set_construction.md`.

### health: 상태 확인

**설명**: `/health`는 프로세스가 살아 있으면 200을 돌려준다. `/ready`는 벡터 DB에 연결되고 인덱스 계약이 서버 설정과 일치할 때만 200, 아니면 503을 돌려준다. compose healthcheck는 `/ready`를 쓴다.

**구현 파일**

| 파일 | 층 | 역할 |
|---|---|---|
| `app/api/health_router.py` | api | 두 엔드포인트 |
| `app/repository/chunk_repository.py` | repository | 컬렉션 메타데이터 조회 |

**테스트**

| 종류 | 파일 |
|---|---|
| 통합 | `tests/integ/test_health.py` |

**제약과 미구현**: 전부 미구현.

### ingest: 색인

**설명**: 원문을 정제, 청크, 임베딩해 벡터 DB에 upsert하고 컬렉션 메타데이터에 인덱스 계약(임베딩 모델, 토크나이저, Chunk 설정 해시)을 기록한다. 같은 입력으로 다시 돌리면 같은 상태로 수렴한다.

**처리 흐름**: `ingest_cli`에서 `ingest_service.run`으로, `document_loader`, `text_cleaner`, `chunk_splitter`(`text_tokenizer`로 길이 측정), `embedding_client`, `chunk_repository.ensure_collection`, `chunk_repository.upsert` 순.

**구현 파일**

| 파일 | 층 | 역할 |
|---|---|---|
| `app/cli/ingest_cli.py` | cli | 명령 진입점 |
| `app/service/ingest/ingest_service.py` | service | 파이프라인 조립 |
| `app/service/ingest/document_loader.py` | service | manifest 순서로 원문을 읽어 정제한 Document로 만듦. 구현됨 |
| `app/service/ingest/text_cleaner.py` | service | front matter, HTML 주석, HTML 태그 제거. Markdown 링크와 `<name>` 같은 자리표시자는 유지(근거 인용과 대조하기 위해). 구현됨 |
| `app/service/ingest/chunk_splitter.py` | service | 고정 길이 분할(`FixedLengthSplitter`) 구현됨. 다른 방식은 Chunking 선정 후 |
| `app/common/text_tokenizer.py` | common | 청크 길이 측정, BM25 토큰화(Query와 공유) |
| `app/client/embedding_client.py` | client | 배치 임베딩(Query와 공유). 지금은 로컬 fastembed 임시 모델 |
| `app/repository/qdrant_chunk_repository.py` | repository | `ensure_collection`, `upsert`, 검색(dense, sparse, RRF 결합). 선정된 DB |
| `app/schema/chunk_schema.py` | schema | Document, Chunk 모델. chunk_id는 (doc_id, text)의 sha256 |
| `app/schema/vector_schema.py` | schema | sparse 벡터, 인덱스 계약 |

**테스트**

| 종류 | 파일 |
|---|---|
| 단위 | `tests/unit/test_ingest_chunk_splitter.py`(정제 포함) |
| 통합 | `tests/integ/test_ingest.py`(미구현) |

**제약과 미구현**: `ingest_service`, `ingest_cli`, 인덱스 계약 기록은 미구현. 길이 단위는 토크나이저 선정, 분할 방식은 Chunking 선정, 모델은 Embedding 선정 후 확정.

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

### query: 질의응답

**설명**: 질문을 받아 인덱스를 검색하고, 검색한 근거만으로 답하며 `[n]` 인용을 출처 정보로 바꿔 돌려준다. 근거가 부족하면 `insufficient_context`를 돌려준다. 저장소에 쓰지 않는다.

**입력과 결과**

| 입력 | 결과 |
|---|---|
| 문서에 근거가 있는 질문 | `status=answered`, 답변, 인용 목록 |
| 검색 최고 점수가 임계값 미만인 질문 | LLM 호출 없이 `status=insufficient_context` |
| 근거는 검색됐지만 답이 없는 질문 | 모델의 근거 부족 토큰을 감지해 `status=insufficient_context` |
| 길이 제한을 넘은 질문 | 422 |
| `API_KEY`가 설정됐는데 `X-API-Key`가 없거나 틀림 | 401 |
| LLM 동시 호출 상한 대기 한도 초과 | 503, `Retry-After` |
| LLM 또는 임베딩 호출 실패, 타임아웃 | 502, 504 |
| 색인과 다른 임베딩 모델, 토크나이저 설정으로 기동 | 기동 실패 |

**처리 흐름**: `query_router`에서 `query_service.answer`로, `chunk_retriever`(`embedding_client`, `text_tokenizer`, `chunk_repository.search`), `evidence_checker`(점수 임계값), `prompt_builder`, `llm_client`, `evidence_checker`(근거 부족 토큰), `citation_parser` 순.

**구현 파일**

| 파일 | 층 | 역할 |
|---|---|---|
| `app/main.py` | api | lifespan에서 클라이언트 조립, 인덱스 계약 검증 |
| `app/api/query_router.py` | api | 요청 검증, 응답 변환 |
| `app/api/request_middleware.py` | api | 요청 ID, 처리 시간 로그 |
| `app/api/api_key_guard.py` | api | `X-API-Key` 검사 |
| `app/api/error_mapper.py` | api | 예외를 HTTP 상태로 변환 |
| `app/service/query/query_service.py` | service | 파이프라인 조립 |
| `app/service/query/chunk_retriever.py` | service | dense 또는 hybrid 검색 |
| `app/service/query/evidence_checker.py` | service | 점수 임계값과 근거 부족 토큰 판정 |
| `app/service/query/prompt_builder.py` | service | 번호 매긴 근거와 지시문 조립 |
| `app/service/query/citation_parser.py` | service | `[n]` 추출, 존재하지 않는 번호 제거 |
| `app/repository/chunk_repository.py` | repository | `search` |
| `app/client/llm_client.py` | client | OpenAI 호환 채팅 호출 |
| `app/client/embedding_client.py` | client | 질의 벡터화 |
| `app/schema/query_schema.py` | schema | 요청과 응답 모델 |

**테스트**

| 종류 | 파일 |
|---|---|
| 단위 | `tests/unit/test_query_citation_parser.py` |
| 단위 | `tests/unit/test_query_evidence_checker.py` |
| 단위 | `tests/unit/test_query_prompt_builder.py` |
| 통합 | `tests/integ/test_query.py` |

**제약과 미구현**: 전부 미구현.

### query_stream: 스트리밍 질의응답

**설명**: `query`와 같은 파이프라인을 쓰고 생성 토큰을 `token` 이벤트로 흘린 뒤, 검증한 인용 목록과 메타를 `final` 이벤트로 보낸다. 검색 단계에서 거절되면 `token` 없이 `final`만 보낸다.

**구현 파일**

| 파일 | 층 | 역할 |
|---|---|---|
| `app/api/query_router.py` | api | SSE 응답 |
| `app/service/query/query_service.py` | service | 생성 단계 스트림 버전 |
| `app/client/llm_client.py` | client | 스트리밍 채팅 호출 |

**테스트**

| 종류 | 파일 |
|---|---|
| 통합 | `tests/integ/test_query_stream.py` |

**제약과 미구현**: 스트리밍 중 흘린 텍스트에는 검증 전 `[n]`이 그대로 있다. 존재하지 않는 번호는 `final`의 인용 목록에서만 빠진다. 전부 미구현.

### selection_run: 선정 실험

**설명**: 데이터셋, 데이터베이스, Embedding, 토크나이저, Chunking, LLM 선정을 위한 실험을 설정 파일 단위로 실행하고 결과 표를 출력한다. Ingest, Query 모듈을 설정만 바꿔 재사용하며 선정에는 dev set만 쓴다. 해석과 결정은 `research/<주제>.md`에 기록한다.

| 실험 | 측정 |
|---|---|
| `profile` | 후보 Corpus별 규모, 구조, 파싱 난이도, 함정 요소 통계. 구현됨 |
| `closed_book` | 후보 Corpus별 근거 없는 질의를 seed별로 반복해 답변 수집. 구현됨 |
| `closed_book_report` | 블라인드 채점 결과를 답변에 붙여 후보별 오답, 모름, 다수결 판정 집계. 구현됨 |
| `tokenizer` | 청크 길이 단위별 임베딩 입력 잘림 비율, BM25 토크나이저별 Hit@5, MRR, 처리 시간 |
| `chunking` | 분할 방식, 크기, 겹침별 Hit@5, MRR, 근거 보존율, 청크 수, 질의당 근거 토큰 수 |
| `database` | 후보 DB별 기능 검사 6종, 적재 시간, 질의 지연 p50과 p95, 메모리 사용량, numpy 전수 비교 대비 ANN 재현율. 구현됨(`make db-bench`) |
| `embedding` | 임베딩 후보별 근거 단위 Hit@5, Hit@10, MRR, 근거 재현율, 문서 단위 Recall@5(영어, 한국어 질의), bootstrap 신뢰구간, 색인 시간, 질의 임베딩 지연. 구현됨(`make embed-bench`). 교차 확인은 미구현 |
| `refusal_threshold` | dev set 답 있음/답 없음 문항의 dense 최고 점수 분포와 임계값별 오거절, 미거절 비율 |
| `llm` | 생성 후보별 Faithfulness, 인용 형식 준수율, 거절률, 문항당 비용과 지연 |

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
| `app/service/eval/embedding_benchmark.py` | service | 모델별 색인, Qdrant 정확 검색, 지표와 bootstrap 구간 |
| `app/service/eval/retrieval_metric.py` | service | 근거 단위 Hit@k, MRR, 근거 재현율, 문서 Recall(60자 창 근거 판정) |
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

**제약과 미구현**: 데이터셋, 데이터베이스, Embedding 외 실험은 미구현. DB 저장소 3종은 실제 DB가 필요해 단위 테스트 대신 `make db-bench`의 기능 검사로 검증한다. 기각된 후보 구현은 실험 재현을 위해 남긴다.

---

## 공통 모듈

| 파일 | 역할 |
|---|---|
| `app/common/logger.py` | structlog 로거. `LOG_FORMAT`으로 콘솔과 JSON 전환 |
| `app/common/settings.py` | pydantic-settings 환경변수 로딩. 키 누락 시 기동 실패 |
| `app/common/content_hasher.py` | 파일, 텍스트, 설정의 sha256 |
| `app/common/text_tokenizer.py` | 선정된 토크나이저. Ingest와 Query가 같은 인스턴스 설정을 씀 |
