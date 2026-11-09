# Elice HR Assignments

## 01. Overview

Citation 기반 RAG QA 서비스와 Eval Harness를 구축한 후 분석된 부분에 대한 개선 실험 및 report를 작성하여 통합 제출하는 HR Assignments 입니다.

uv(Python 패키지 관리자) 공식 문서를 근거로 질문에 답하고, 답의 문장마다 출처를 붙이며, 근거가 없으면 답하지 않는 질의응답 서비스입니다. 같은 저장소에 구성 요소를 고른 선정 실험(1~9단계), Gold Set 기반 평가(10, 11단계), 실제 질의를 누적해 보여주는 실시간 평가 대시보드가 함께 있습니다.

| 카테고리 | 세부 설정 값 | 비고 |
| :----: | :-------: | :-:|
| Corpus | astral-sh/uv `docs/` (commit `5ce34500b8a3`, 문서 81개, 약 181쪽) | 후보 4개 중 다중 문서, 요약, 함정 문항을 만들 수 있는 유일한 후보. [01](project_planning/experiments/01_dataset.md) |
| LLM | claude-haiku-5-5 (엘리스 ML API Serverless) | 품질 하한을 넘은 유일한 후보, 문항당 약 ₩0.9. [09](project_planning/experiments/09_llm.md) |
| Judge LLM | gemini-3.8-flash | 답변 모델과 다른 계열(자기 선호 편향 완화) |
| Embedding | Qwen/Qwen3-Embedding-0.6B (fastembed, 로컬 CPU) | 엘리스 라이브러리에 임베딩 모델이 없어 오픈소스 6종 비교. [04](project_planning/experiments/04_embedding.md), [07](project_planning/experiments/07_embedding_crosscheck.md) |
| Vector DB | Qdrant `v1.20.0` | BM25 IDF와 RRF 결합을 서버가 제공. [03](project_planning/experiments/03_database.md) |
| Tokenizer | 청크 길이: Qwen3 토큰 / BM25: `word` | [05](project_planning/experiments/05_tokenizer.md) |
| Chunking | 문서 구조 분할, 512토큰, 겹침 77토큰(`structure-512-77`) | [06](project_planning/experiments/06_chunking.md) |
| 거절 임계값 | dense 최고 점수 0.6375 | dev set 오거절 0%에서 가장 낮은 값. [08](project_planning/experiments/08_prompt_and_refusal.md) |
| QA Set | dev set 38문항(선정용), test set 40문항(평가용), 각각 한국어 번역 묶음 | 근거 구절을 공유하는 문항 없음. [data/gold/README.md](data/gold/README.md) |
| 평가 기록 저장소 | PostgreSQL `17.6-alpine` | Gold Set 평가와 실시간 질의 기록 |

## 02. How to use?

### 02-1. Install

필요한 것: Docker와 Docker Compose, `make`, git. Python 패키지는 uv(`pyproject.toml`, `uv.lock`)로 이미지 안에 설치되므로 호스트에 Python이 없어도 됩니다. 로컬에서 테스트만 돌릴 때는 `uv sync`를 씁니다.

```bash
git clone https://github.com/ash-hun/assignments-choijaehun.git
cd assignments-choijaehun
cp .env.example .env            # 아래 환경변수를 채운다
make build                      # 이미지 빌드(runtime, korean, dev 단계)
make corpus                     # 고정 commit의 uv 문서를 받고 sha256을 manifest와 대조
make ingest                     # Qdrant를 띄우고 청크, 임베딩, 색인(CPU 약 5분). 다시 돌려도 같은 상태
make serve                      # API 서버(http://localhost:8000), 대시보드(http://localhost:8000/dashboard)
make eval                       # test set 평가와 Judge 판정, reports/<run_id>/에 Report
make stop                       # api, qdrant, evaldb 정지
```

검증 명령:

| 명령 | 내용 |
|---|---|
| `make test`, `make typecheck` | 네트워크를 끊은 컨테이너에서 pytest(외부 API는 모두 mock), mypy strict |
| `make validity` | 일부러 망가뜨린 변형 5종으로 지표가 실제로 떨어지는지 검증 |
| `make label-sheet`, `make agreement` | 사람 라벨 시트 생성, 사람 라벨 대비 Judge 일치율과 Cohen's kappa |
| `make gold-draft SPLIT=test`, `make gold-translate SPLIT=test`, `make gold-check SPLIT=test LANG_CODE=en` | Gold Set 초안, 번역 묶음, 검증 |

환경변수(`.env`):

| 이름 | 필수 | 설명 |
|---|---|---|
| `ELICE_SERVERLESS_API_KEY` | 예 | 엘리스 ML API Serverless 키 |
| `ANSWER_LLM_BASE_URL` | 예 | 답변 모델(claude-haiku-5-5) 엔드포인트. 형식 `https://mlapi.run/<endpoint-id>/v1` |
| `JUDGE_LLM_BASE_URL` | 평가 시 | Judge 모델(gemini-3.8-flash) 엔드포인트. 없으면 `LLM_CANDIDATE_URLS`의 같은 이름 항목을 쓴다 |
| `EVAL_DB_PASSWORD` | 평가 시 | 평가 기록 저장소 비밀번호(예: `openssl rand -hex 24`). 없으면 API는 실시간 평가만 끄고 뜬다 |
| `LLM_BASE_URL`, `LLM_MODEL` | Gold Set 초안 생성 시 | 초안과 번역에 쓴 모델(gpt-6.1-terra) |
| `LLM_CANDIDATE_URLS` | LLM 선정 실험 시 | 모델명을 키로 하는 JSON |
| `API_KEY` | 아니오 | 설정하면 `/v1/*` 요청에 `X-API-Key`가 필요하다 |
| `GITHUB_TOKEN` | 아니오 | GitHub API 호출 한도를 넘을 때만 |
| `LOG_FORMAT` | 아니오 | `console`(개발) 또는 `json`(운영) |

재현 시 주의:

- `make eval`의 run_id는 설정, Gold 파일, 원문, 인덱스 계약, 모델, 프롬프트의 해시입니다. 같은 run_id면 저장소에 기록된 문항과 판정은 다시 부르지 않아 비용이 0이고 같은 Report가 나옵니다.
- 새 환경에서 처음 돌리면 답변 생성(약 ₩80)과 Judge(약 ₩2,600)를 새로 부릅니다. 두 모델 모두 게이트웨이가 `seed`를 거부해(400) temperature 0으로만 고정했으므로, 생성 문구와 판정이 일부 달라질 수 있습니다. 커밋된 Report(`reports/`)가 이 README의 수치 출처입니다.

### 02-2. Endpoint

| Method | Path | 설명 |
|---|---|---|
| `POST` | `/v1/query` | 질의응답. 근거가 없으면 `status=insufficient_context`(200) |
| `POST` | `/v1/query/stream` | 같은 질의응답의 SSE 스트리밍(`token`, `final`, `error` 이벤트) |
| `GET` | `/v1/metrics` | 실시간 누적 지표(JSON) |
| `GET` | `/v1/metrics/stream` | 실시간 누적 지표(SSE) |
| `GET` | `/dashboard` | 실시간 평가 대시보드 |
| `GET` | `/health`, `/ready` | 생존 확인, 벡터 DB 연결과 인덱스 계약 일치 확인 |

```bash
curl -s localhost:8000/v1/query -H 'Content-Type: application/json' \
  -d '{"question": "How do I change where uv stores its cache?"}'
```

```json
{
  "status": "answered",
  "answer": "Set the UV_CACHE_DIR environment variable ... [1]",
  "citations": [{"ref": 1, "doc_id": "concepts/cache.md", "title": "...", "url": "https://github.com/astral-sh/uv/blob/5ce34500b8a3/docs/concepts/cache.md", "chunk_id": "...", "snippet": "..."}],
  "meta": {"model": "claude-haiku-5-5", "retrieval_scores": [0.81, ...], "dropped_citations": 0, "latency_ms": 4613, "retrieval_ms": 143, "first_token_ms": null, "usage": {"input_tokens": 3952, "output_tokens": 599}}
}
```

요청 본문, 에러 코드(401, 422, 502, 503, 504), 다시 호출했을 때의 동작은 [docs/api_spec.md](docs/api_spec.md), 대시보드 화면은 [docs/view_spec.md](docs/view_spec.md), 기능별 구현 파일과 테스트는 [docs/features.md](docs/features.md)에 있습니다. 서버의 `/docs`에서 OpenAPI 문서를 볼 수 있습니다.

## 03. Experiments

모든 실험은 판정 규칙을 실행 전에 문서에 적고, 결과를 본 뒤 규칙과 다르게 정한 경우는 각 문서의 "계획과 달라진 점"에 남겼습니다. 차이는 문항 bootstrap 95% 구간(2,000회, seed 2026)으로 판정합니다. 전체 목록은 [project_planning/experiments/README.md](project_planning/experiments/README.md)입니다.

### 03-1. 선정 실험(dev set)

| 단계 | 결정 | 근거 요약 |
|---|---|---|
| 1. 데이터셋 | uv 문서 | 후보 4개 중 문서의 88%가 다른 문서를 참조해 다중 문서 문항이 성립하고, 버전 표기와 정확한 식별자가 많다 |
| 2. dev set | 38문항 + 한국어 번역 | LLM 초안을 전부 검수, 4문항 교체 |
| 3. 벡터 DB | Qdrant | Chroma는 기능 검사 탈락, pgvector와는 운영 단순성(BM25 IDF와 RRF를 서버가 제공)에서 갈림 |
| 4, 7. 임베딩 | Qwen3-Embedding-0.6B | e5와 주 지표가 같았으나 최대 입력 32,768토큰. 확정 Chunking에서 e5는 청크 33%가 잘려 근거 보존@5가 0.10~0.13 낮음 |
| 5. 토크나이저 | 청크 길이 Qwen3 토큰, BM25 `word` | |
| 6. Chunking | `structure-512-77` | 사전 규칙은 재귀 분할이었으나 Hit@5와 근거 보존@k로 바꿈(문서에 이유 기록) |
| 8. 거절 임계값 | 0.6375 | dev set 오거절 0%에서 답 없는 문항을 가장 많이 거름 |
| 9. LLM | claude-haiku-5-5 | gemini-3.8-flash는 한국어 오거절 0.133으로 품질 하한(10%) 미달 |

### 03-2. 성능 평가(test set, 기준선)

평가 대상은 API와 같은 조립의 실제 질의 경로이고, `make eval` 한 번으로 돕니다. Report: [reports/baseline-4e6abaee3113/summary.md](reports/baseline-4e6abaee3113/summary.md)

| 지표 | 영어 | 한국어 |
|---|---|---|
| Recall@5 | 0.773 [0.648, 0.891] | 0.703 [0.560, 0.834] |
| MRR@10 | 0.762 | 0.715 |
| nDCG@10 | 0.751 | 0.684 |
| uv 답변 정확성(답한 문항 중 정답) | 0.742 [0.581, 0.903] | 0.607 [0.429, 0.786] |
| 답 없는 문항 거절률 | 1.000 | 1.000 |
| 답 있는 문항 오거절률 | 0.031 | 0.097 |
| TTFT 중앙값 / Latency 중앙값 | 2.4초 / 3.5초 | 3.5초 / 5.3초 |
| 문항당 비용 | ₩0.92 | ₩1.03 |

- multi_doc 문항이 가장 약합니다(정확성 영어 0.600, 한국어 0.333). 두 문서 중 한쪽 근거만 찾는 경우가 많습니다. [10](project_planning/experiments/10_retrieval_eval.md), [11](project_planning/experiments/11_generation_eval.md)
- 답한 59건 중 8건(14%)이 생성 출력 상한(1,500토큰)에서 잘렸고, 그중 1건만 정답이었습니다.

### 03-3. 지표 선정과 Judge 신뢰성

RAGAS, ARES, RAGChecker, TruLens를 조사해 지표를 정하고([research/gold_metric_selection.md](research/gold_metric_selection.md)), Judge 지표는 네 가지 조건을 모두 통과해야 채택했습니다.

| 조건 | 방법 | 기준 |
|---|---|---|
| 반응성 | 일부러 망가뜨린 변형 5종(무작위 청크, 거절 끔, 인용 섞기, 근거 바꿔치기, 인용 지우기)에서 지표가 떨어지는지 | 짝지은 차이 95% 구간이 0을 포함하지 않음. 5종 모두 통과 |
| 변별력 | 기준선 통과율 | 1.0이나 0.0이 아님 |
| 일관성 | 같은 입력 3회 판정 | 항목별 일치율 0.90 이상 |
| Human Alignment | 사람 라벨 20건(작성자 직접) | 항목별 Cohen's kappa 0.60 이상 |

| 지표 | 결과 | 결정 |
|---|---|---|
| uv 답변 정확성(핵심 요점을 모두 담고 금지 내용이 없음) | 3회 일치 1.000 / 0.964, kappa 0.886 | 채택 |
| Refusal Accuracy | 규칙 기반 | 채택 |
| Citation Precision | 일치율 0.984지만 kappa 0.494(사람 라벨 126개 중 반례 1개뿐인 kappa 역설). 문구를 한 번 고쳐 다시 잼 | 참고값 |
| uv 답변 품질 점수(6항목) | 5항목은 기준선 통과율 1.000, "근거 없는 주장 없음"은 3회 일치 0.839 / 0.821 | 채택 항목 없음, 항목별 참고값 |

파일럿에서 Judge 출력이 게이트웨이의 비스트리밍 출력 상한(2,000토큰)에 걸려 JSON이 끊기는 문제를 찾아, Judge 호출을 스트리밍으로 바꾸고 인용을 8개씩 나눠 판정합니다.

### 03-4. 실시간 누적 평가

`/v1/query`, `/v1/query/stream` 응답 뒤 기록을 남기고, API 프로세스 안의 백그라운드 Judge가 예산(기본 ₩3,000) 안에서 1회 판정합니다. 대시보드는 지표별 누적 평균, 95% 구간(비율은 Wilson), 최근 50건 이동 평균, 같은 구성의 Gold Set 기준선과 기준선이 누적 구간 안에 있는지(표본 10건 이상부터)를 보여주고, 최근 질의 100건을 10건씩 표로 보여줍니다(질문과 답 원문 제외). 정답이 없는 실시간 질의에서는 채택된 Judge 지표가 없어 Judge 항목은 참고값으로 표시합니다.

### 03-5. Part C 개선 실험

(진행 예정) 가설: dense 검색에 BM25를 RRF로 결합하면 multi_doc 문항의 근거 누락과 trap 문항의 낮은 nDCG(영어 0.572)가 줄어 uv 답변 정확성이 오른다. 같은 test set과 Harness로 기준선과 짝지어 비교합니다.

## 04. Architecture

```
            ┌──────────────── 오프라인(쓰기) ────────────────┐
make corpus │ GitHub(고정 commit) → manifest sha256 대조 → data/corpus/raw │
make ingest │ 정제 → 문서 구조 분할(512/77) → Qwen3 임베딩 + BM25 → Qdrant upsert │
            │   컬렉션 메타데이터에 인덱스 계약(임베딩, 토크나이저, Chunk 설정) 기록   │
            └──────────────────────────────────────────────┘
                                   │ 인덱스 계약 일치해야 기동
            ┌──────────────── 온라인(읽기) ─────────────────┐
POST /v1/query(/stream)                                             │
  → 질의 임베딩 → Qdrant dense top-5 → 최고 점수 < 0.6375면 거절(LLM 미호출)
  → 번호 매긴 근거로 프롬프트 → claude-haiku-5-5 → INSUFFICIENT_CONTEXT면 거절
  → [n] 인용 검증(없는 번호는 지움) → 출처 목록과 함께 응답              │
  → (응답 뒤) 평가 기록 저장 → 백그라운드 Judge → 누적 집계 → /dashboard
            └──────────────────────────────────────────────┘
make eval   test set → 같은 질의 경로(스트리밍) → 검색 지표, 거절, 운영 수치
            → Judge(gemini-3.8-flash, 3회 다수결) → PostgreSQL + reports/<run_id>/
```

- compose 서비스: `qdrant`(색인), `evaldb`(평가 기록), `api`(uvicorn, `127.0.0.1:8000`만 공개), `batch`(일회성 배치), `dev`(네트워크 없는 테스트). DB는 포트를 열지 않습니다.
- 코드 층: `api` → `service` → `repository`, `client` → `schema`, `common`. 의존은 한 방향입니다. 상세는 [project_planning/architecture.md](project_planning/architecture.md)입니다.

## 05. Design Decisions & Trade-offs

| Design Decisions                                    | Benefit Factor                                       | Lost Factor                                |
| --------------------------------------------------- | ---------------------------------------------------- | ------------------------------------------ |
| LangChain, LlamaIndex를 쓰지 않고 검색, 프롬프트, 인용 파싱을 직접 구현 | 단계별 동작을 설명할 수 있고, 평가에 중간 산출물(검색 점수, 지운 인용 수)을 그대로 기록 | 구현량                                        |
| 거절을 두 단계로(dense 점수 임계값, 모델의 근거 부족 토큰)               | 근거가 없으면 LLM 비용 0, 응답 88ms                            | 임계값 근처 질의는 판정이 흔들림(한국어는 12.8%가 ±0.05 구간)   |
| 인덱스 계약을 기동 시 검증                                     | 임베딩, 토크나이저가 어긋난 채 품질만 조용히 떨어지는 상태를 막음                | 설정을 바꾸면 다시 색인해야 함                          |
| Ingest를 HTTP로 열지 않음                                 | 공개 API는 읽기 전용이고, 평가 중 인덱스가 바뀌지 않음                    | 문서 갱신은 배치 재실행으로만                           |
| 선정에는 dev set, 평가에는 test set                         | 같은 문항으로 고르고 평가해 점수가 부풀려지는 것을 막음                      | 문항 수가 나뉘어 구간이 넓음                           |
| 판정 규칙을 실행 전에 기록                                     | 결과를 보고 규칙을 고르는 것을 막음                                 | 규칙이 틀렸을 때(6단계) 바꾼 이유를 따로 설명해야 함            |
| Judge 점수 대신 항목별 이진 판정을 모아 지표화                       | 호출마다 척도가 흔들리지 않음                                     | Judge 호출과 프롬프트가 길어짐                        |
| 검증을 통과한 Judge 지표만 채택                                | 숫자가 측정하려는 것을 잰다고 말할 수 있음                             | 품질 점수를 내지 못함. 채택 생성 지표가 정확성과 거절 둘뿐         |
| 평가 기록 저장소를 캐시로 사용(같은 run_id면 다시 부르지 않음)             | 재실행 비용 0, 중간 실패 시 재실행으로 이어서 진행                       | seed를 고정할 수 없어 저장소가 없는 새 환경에서는 값이 달라질 수 있음 |
| 임베딩을 로컬 CPU(fastembed)로                             | API 비용 0, 엘리스 라이브러리에 임베딩 모델이 없음                      | 질의 임베딩 지연(검색 지연 중앙값 약 0.2초)                |
| 가장 저렴한 품질 통과 모델(Haiku)                              | 문항당 약 ₩0.9(Gemini의 1/5)                              | 출력 상한에서 긴 답이 잘림                            |

## 06. Limitations & Known Issues

- **답 잘림**: 답한 59건 중 8건이 생성 출력 상한 1,500토큰에서 잘립니다(주로 한국어 요약, 다중 문서). 기준선은 그대로 재고 결함으로 기록했습니다.
- **게이트웨이 WAF 차단**: 한국어 test 문항 1개가 엘리스 게이트웨이 앞단의 Cloudflare WAF에 매번 403으로 막힙니다. 같은 질문을 실제 사용자가 해도 502가 납니다. 원인은 확인하지 못했습니다.
- **TPOT**: 1~2ms로 측정돼 생성 속도보다 빠릅니다. 게이트웨이가 스트림을 묶어 보내는 것으로 추정하며, 생성 속도가 아니라 전달 속도에 가깝습니다.
- **Judge 지표**: Citation Precision과 품질 항목은 검증 조건을 통과하지 못해 참고값입니다. 사람 라벨은 작성자 한 명의 20건이라 라벨러 사이 일치도는 재지 않았습니다.
- **한국어 평가**: 한국어 묶음은 질문만 번역했고 정답 기준은 영어입니다.
- **실시간 평가**: 저장소 연결 하나와 Judge 작업자 하나로 동작합니다. API를 여러 워커로 띄우면 연결 풀과 작업자 분리가 필요합니다. 동시 처리량(Throughput)은 재지 않았습니다.
- **재현성**: LLM `seed`를 쓸 수 없어 저장소와 캐시 없이 새로 돌리면 생성과 판정이 일부 달라질 수 있습니다.

## 07. Future Work

- Part C: Hybrid 검색(dense + BM25, RRF)으로 multi_doc, trap 문항 개선
- 생성 출력 상한 조정과 답 길이 지시(잘림 14% 해소)
- 한국어 질의 번역 후 검색(한국어 오거절 0.097, 검색 손해)
- 문서 단위 증분 Ingest API(비동기 작업, 인증, 동시 Ingest 잠금)
- CI 회귀 게이트: PR마다 캐시와 함께 test set 일부를 돌려 기준 Report와 bootstrap 구간으로 비교
- 사람 라벨 확대(라벨러 2인 이상)와 Judge 문구 재검증으로 품질 항목 재채택

## 08. Cost

엘리스 ML API 크레딧으로 진행했습니다(VAT 별도, 캐시 할인 미반영).

| 작업 | 비용 |
|---|---|
| LLM 선정 실험(Haiku, Gemini) | 약 ₩420 |
| test set 답변 생성(기준선, 변형 5종) | 약 ₩280 |
| Judge(파일럿, 기준선 3회, 변형 5종, 재작업 포함) | 약 ₩6,700 |
| 실시간 평가 확인 | 약 ₩55 |

임베딩은 로컬 모델이라 비용이 없습니다. 비용 때문에 답변 모델은 품질 하한을 넘는 후보 중 가장 저렴한 모델을, Judge 표본은 Gold Set 3회, 변형과 실시간 1회로 정했습니다.

## 09. Basic Ruleset

기본적으로 GitHub 공개 Repository 링크를 제출해야하며, 아래 항목들을 포함해야 한다.

1. README.md:
   - 재현 가능한 실행 방법 설치 Ingest 서버 실행 Eval 실행 순서 및 필요 환경 변수 안내
   - 사용한 데이터셋, 모델, 프레임워크 기술 스택 선정 근거
   - 시스템 아키텍처 개요 다이어그램 또는 텍스트 설명
   - 개발 과정에서의 핵심 Design Decision 및 Trade off 분석 기록
   - 현재 아키텍처의 한계점, 알려진 이슈, 향후 개선 과제
2. Source Code: 동작하는 파이프라인 코드, Eval 스크립트, Gold Set 데이터
3. Commit History: 의미 있는 단위의 점진적인 Commit 히스토리 (단일 Commit으로 전체 코드 제출 지양)

또한, 하기 FAQ를 참고하여 수행하길 권장한다.

1. AI 도구 활용: Copilot, ChatGPT 등의 사용은 현업 실무와 동일하게 적극 허용합니다. 단, 제출된 모든 산출물의 설계 판단은 본인이 완벽히 이해하고 설명할 수 있어야 합니다. 기술 인터뷰 시 왜 해당 아키텍처 및 로직을 채택했는지 심층 검증이 진행됩니다.
2. Framework 활용: LangChain, LlamaIndex 등의 사용은 자유로우나, 이를 Blackbox처럼 사용하지 않고 내부 파이프라인에서 어떠한 과정이 일어나는지 정확히 파악하고 있어야 합니다.
3. 시간 배분: 과제의 범위가 넓다고 판단될 경우, Part AAPI 구현 는 동작 가능한 최소한의 수준MVP으로 마무리하고 Part BEval와 Part C실험 및 분석 에 집중하시기 바랍니다.
4. 비용 한도: 본 과제의 API 및 컴퓨팅 비용은 컴퓨팅 · API 비용 지원 섹션의 안내에 따라 엘리스AI클라우드 크레딧으로 지원받을 수 있습니다. 그 외에도, 저렴한 모델이나 오픈소스 모델을 활용해도 무방합니다. 비용 또는 컴퓨팅 제약으로 인해 특정 모델을 선택했다는 점을 README.md에 명시 해주신다면, 합리적인 Trade off 판단으로 인정될 경우 긍정적으로 평가합니다.
