# 수행 계획: 문서 기반 RAG QA 서비스와 자체 Eval Harness

원문: `project_planning/baseline/elice_project_2026.pdf` (6쪽). 아키텍처: `project_planning/architecture.md`.

## 과제 요구사항 정리

평가자가 보는 축은 세 가지다. 생성형 AI 품질을 어떻게 정의했는가, 어떻게 측정했는가, 개선 결과를 데이터로 어떻게 증명했는가. 

### 공통 제약

| 항목 | 요구 |
|---|---|
| Corpus | 공개 문서셋(권장), 사내 문서, Synthetic 중 하나. 선택 이유를 README에 기록 |
| 규모 | Hallucination이 관찰될 규모. 문서 20개 이상 또는 총 50페이지 이상 |
| 재현성 | 데이터를 저장소에 포함하거나 자동 다운로드 스크립트 제공 |
| 비용 | 엘리스AI클라우드 크레딧 5만원 한도. 저렴한 모델 선택 시 README에 근거 기록 |
| 비밀값 | API Key는 환경변수로 분리. 공개 저장소에 올리지 않음 |
| 프레임워크 | LangChain 등 사용 가능하나 내부 동작을 설명할 수 있어야 함 |
| 면접 | "왜 이 아키텍처와 로직을 택했는가"를 심층 검증 |

### Part A 필수와 가산

- 필수: Ingest Pipeline, Chunking 전략과 근거, Embedding과 Index, 검색과 답변 생성 API, Citation, Request/Response Schema
- 기대: 근거 부족 시 응답 불가 반환, 비밀값 환경변수 분리, Streaming(가산점)

### Part B 필수와 가산

- Gold Set: 20개 이상 질의와 기대 근거 또는 수용 기준. 요약, 추론 같은 생성형 질의 포함. 구축 방법, 편향, 한계 명시
- Metric: 2개 이상 정의와 선정 이유. LLM-as-a-Judge를 쓰면 신뢰성, 일관성, Human Alignment 확보 방법 설명
- 자동화: 단일 명령으로 전체 평가와 요약 Report 생성. Seed와 모델 버전 기록으로 재현 가능
- 기대: Metric 한계와 맹점 기록, CI 연동 시 Regression 방지 설계 논의(가산점)

### Part C 필수

- 개선 가설 1개 이상 적용 후 Part B Harness로 Before/After 비교
- README에 Hypothesis, Result(표 또는 그래프), Analysis, Next Steps
- 지표 개선 자체는 필수가 아니다. 가설, 측정, 해석의 논리성이 평가 대상

### 제출물

- GitHub 공개 저장소 링크(전형 안내 이메일과 같은 주소로 제출)
- README: 재현 절차(설치, Ingest, 서버 실행, Eval 실행 순서)와 환경변수, 기술 선정 근거, 아키텍처 개요, Design Decision과 Trade-off, 한계와 향후 과제, Part C 실험
- Source: 파이프라인 코드, Eval 스크립트, Gold Set 데이터
- 의미 단위의 점진적 Commit 히스토리. 단일 Commit 제출 지양

## 전체 구조 방향

시스템은 두 경로로 명시적으로 나뉜다.

| 경로 | 성격 | 흐름 | 진입점 |
|---|---|---|---|
| Ingest | 쓰기, 오프라인 배치 | 문서, 정제, 청크, 임베딩, 인덱스 저장 | `make ingest` (compose 일회성 서비스 `docker compose run --rm batch`) |
| Query | 읽기, 온라인 요청 | 질문, 검색, LLM 답변 생성, Citation 반환 | FastAPI 서버 `POST /v1/query`, `POST /v1/query/stream` |

Ingest를 질의 요청 경로 밖에서 돌리는 이유: 질의마다 정제와 임베딩을 하면 지연과 비용이 Corpus 크기에 비례해 늘어난다. Ingest를 HTTP로 열지 않는 이유: 과제가 API로 요구하는 것은 질의뿐이고, 평가 중 인덱스가 바뀌면 Before/After 비교가 무너지며, 쓰기 엔드포인트는 인증과 비동기 작업 관리를 새로 요구한다. 문서 단위 증분 Ingest API는 README 향후 과제에 설계로 남긴다. "오프라인"은 로컬에서 손으로 돌린다는 뜻이 아니다. API 서버와 같은 이미지를 쓰는 compose 일회성 서비스로 실행해 재현 절차를 compose 하나로 끝낸다.

두 경로가 공유하는 것은 인덱스(벡터 DB 컬렉션)와, 반드시 같아야 하는 두 설정(임베딩 모델, 토크나이저)뿐이다. Ingest가 컬렉션 메타데이터에 이 두 값을 기록하고, Query는 기동 시 자기 설정과 비교해 다르면 기동을 거부한다. 색인과 질의의 임베딩 모델이 어긋나면 검색이 조용히 망가지기 때문이다.

- 언어와 도구: Python, FastAPI, pydantic, uv, Docker Compose, pytest, mypy, structlog
- LLM과 Embedding 호출: OpenAI SDK로 엘리스 ML API Serverless 엔드포인트 직접 호출. LangChain 미사용
- Vector DB: Qdrant(gRPC 연결)로 확정(`research/database_selection.md`). 이후 실험은 모두 Qdrant 위에서 돌린다
- 고정 순서 파이프라인이라 에이전트가 아니다. LangGraph 미도입

## 선정 실험 (필수)

설계 시점에 확정하지 않는다. 아래 항목은 실험이나 조사 기록을 남긴 뒤에만 확정한다.

### Part A 선정 실험과 진행 순서

| 순서 | 단계 | 고정한 값 | 주 지표 | 기록 |
|---|---|---|---|---|
| 1 | 데이터셋 선정 | closed-book 모델(기록에 명시) | 적합성 기준, closed-book 오답률 | `research/dataset_selection.md` |
| 2 | dev set 작성(38문항) | Corpus | 없음 | `research/dev_set_construction.md`, `data/gold/dev_set.jsonl` |
| 3 | 데이터베이스 선정 | 임시 임베딩, 고정 길이 청크 | 기능 통과 여부(sparse 적재 포함), ANN 재현율, 지연, 메모리 | `research/database_selection.md` |
| 4 | Embedding 선정 | DB, 고정 문자 길이 청크, dense 검색 | 근거 단위 Hit@5, MRR | `research/embedding_selection.md` |
| 5 | 토크나이저 선정 | DB, 임베딩, 고정 길이 청크 | 잘림 비율, BM25 Hit@5 | `research/tokenizer_selection.md` |
| 6 | Chunking 전략 선정 | DB, 임베딩, 토크나이저. 크기 상한은 임베딩 최대 입력 | Hit@5, 근거 보존율, 근거 토큰 수 | `research/chunking_selection.md` |
| 7 | Embedding 교차 확인 | 확정된 Chunking | 상위 2개의 Hit@5 순위 유지 여부 | `research/embedding_selection.md`에 추가 |
| 8 | 프롬프트, 인용 파서, 거절 판정 구현과 임계값 보정 | 확정된 검색 전체 | 답 있음/답 없음 문항의 dense 최고 점수 분포 | `research/refusal_threshold.md` |
| 9 | LLM 선정 | 검색 결과, 프롬프트, 임계값 | 인용 형식 준수율, 거절률, 비용, 첫 토큰 지연 | `research/llm_selection.md` |

기록 양식은 모두 같다: 질문, 후보, 고정한 변인, 방법, 결과 표, 결정, 기각한 후보와 이유, 재현 명령. README의 기술 선정 근거는 이 기록에 링크한다.

### 공통 원칙

- **dev set만 쓴다**: 선정은 dev set으로 하고 최종 보고는 test set으로 한다. 같은 셋으로 고르고 평가하면 그 셋에 맞춘 선택이 되어 점수가 부풀려진다.
- **한 번에 한 변인**: 실험마다 비교 대상 하나만 바꾸고 나머지는 고정한다. 앞 단계에서 확정한 값을 다음 단계의 고정 변인으로 쓴다.
- **검색 주 지표는 근거 단위**: 검색된 청크에 `gold_evidence` 구절이 들어 있는지로 Hit@k를 판정한다. 근거 구절은 텍스트라 청크 크기가 달라도 같은 기준으로 비교된다. 문서 단위 Recall은 긴 문서에서 아무 청크나 걸려도 성공으로 세어 후보 간 차이를 가리므로 보조 지표로만 둔다.
- **판정 규칙**: 주 지표 차이가 bootstrap 95% 신뢰구간 안이면 차이 없음으로 보고 다음 기준(비용, 단순성 등)으로 넘어간다.
- **파이프라인 재사용**: 실험 전용 코드를 따로 만들지 않는다. Ingest와 Query 모듈을 설정만 바꿔 돌린다.
- **후보는 2~4개**: 크레딧과 시간 안에서 조합 수를 통제한다.

### dev set 구성

| 구분 | 문항 수 | 필드 | 쓰는 단계 |
|---|---|---|---|
| 답 있음 | 30 | question, type, gold_doc_ids, gold_evidence | 3~9 |
| 답 없음 | 8 | question, type, answerable=false | 8, 9 |

수용 기준(acceptance_criteria)은 dev set에 쓰지 않는다. 선정 실험은 검색과 형식 준수만 보므로 라벨링 부담을 줄인다. test set과는 같은 근거 구절을 공유하는 문항이 없게 분리한다.

### 1. 데이터셋 선정

| 항목 | 내용 |
|---|---|
| 질문 | 어떤 Corpus가 과제 제약을 만족하면서 Hallucination과 검색 난이도를 가장 잘 드러내는가 |
| 후보 | 사용자가 수집 중인 후보 전부 |
| 정량 검증 | 후보마다 문서에서 질문 10개를 뽑아 생성 모델 하나에 근거 없이(closed-book) 묻고 오답률을 잰다. 모든 후보에 같은 모델을 쓰고 모델명을 기록한다. 문서 수, 총 토큰 수, 제목 계층 깊이 통계를 함께 기록 |
| 한계 기록 | 최종 생성 모델은 9단계에서 정하므로, 다른 모델에서는 오답률이 달라질 수 있다 |
| 산출물 | `research/dataset_selection.md`, `data/corpus/manifest.json` |

적합성 기준:

| 기준 | 확인 방법 | 탈락 조건 |
|---|---|---|
| 규모 | 문서 수, 총 페이지 또는 토큰 수 | 문서 20개 미만이면서 50페이지 미만 |
| Hallucination 관찰 가능성 | closed-book 오답률 | 모델이 근거 없이도 거의 전부 맞힘 |
| 재현성 | 특정 commit, 버전, 날짜로 고정해 다운로드 가능한지 | 고정 불가, 로그인 필요 |
| 라이선스 | 공개 저장소에 원문 또는 다운로드 스크립트를 둘 수 있는지 | 재배포 금지이고 스크립트로도 받을 수 없음 |
| 파싱 난이도 | 원문 형식과 제목 계층 | 표, 이미지 위주라 텍스트 추출 손실이 큼 |
| 질문 다양성 | 사실, 다중 문서 종합, 요약, 답 없음, 함정 문항을 각각 만들 수 있는지 | 다중 문서 종합 질문이 만들어지지 않음 |
| 함정 요소 | 버전별 차이, 유사 용어, 고유 식별자 존재 | 없음(Part C Hybrid 가설 검증이 약해짐) |
| 언어 | 한국어 여부 | 탈락 조건 아님. 토크나이저 후보 범위에 영향 |

### 3. 데이터베이스 선정

| 항목 | 내용 |
|---|---|
| 질문 | 이 서비스의 기능 요구를 만족하면서 운영이 가장 단순한 벡터 DB는 무엇인가 |
| 후보 | Qdrant, PostgreSQL+pgvector, Chroma. 통과 후보가 없으면 OpenSearch 추가 검토 |
| 기능 조사(통과/탈락) | 자연 키 upsert, 컬렉션 단위 메타데이터 저장(인덱스 계약), **클라이언트에서 직접 토큰화한 sparse 벡터의 적재와 검색**, dense와 sparse 결합 검색, 메타데이터 필터, 정확 검색 모드(4단계용), Python async 클라이언트, Docker 이미지 버전 고정 |
| 입력 데이터 | 선정된 Corpus를 고정 길이로 자른 청크, 임시 임베딩 벡터. 임베딩 후보 차원이 다르면 대표 차원 두 가지(예: 1024, 1536)로 각각 측정 |
| 실험 | 후보마다 같은 데이터를 적재하고 적재 시간, 질의 지연 p50과 p95(dev set 질의 반복 100회), 메모리 사용량(`docker stats`), ANN 재현율(numpy 전수 비교 top-10 대비 일치율) 측정 |
| 판정 | 기능 조사 통과 후보 중 ANN 재현율 0.99 이상, 그다음 운영 단순성(구성 요소 수, 설정량), 그다음 지연 |
| 산출물 | `research/database_selection.md`, 선정 DB의 `chunk_repository` 구현, compose 서비스 추가 |

sparse 적재를 통과 조건으로 두는 이유: BM25 토크나이저는 5단계에서 고른다. DB가 내장 분석기만 허용하면 5단계에서 고른 토크나이저를 쓸 수 없다.

임시 임베딩을 써도 되는 이유: 이 실험은 검색 품질이 아니라 기능, 지연, 자원, 근사 검색 오차를 본다. 이 값들은 벡터의 의미가 아니라 개수와 차원에 좌우된다.

예상(추정): 수천 청크 규모에서는 후보 간 지연과 재현율 차이가 작을 가능성이 높다. 그 경우 실험은 "성능은 결정 요인이 아니다"를 수치로 확인하는 역할이고, 결정은 기능과 운영 단순성으로 한다.

### 4. Embedding 선정

| 항목 | 내용 |
|---|---|
| 질문 | 이 Corpus에서 질의에 맞는 근거를 가장 잘 찾는 임베딩 모델은 무엇인가 |
| 조사 | 엘리스 모델 라이브러리 제공 여부, 최대 입력, 차원, 다국어 지원, 단가. 미제공 시 로컬 오픈소스(bge-m3, multilingual-e5) |
| 청킹 | 고정 문자 길이, 겹침 없음. 길이는 최대 입력이 가장 짧은 후보에서도 잘리지 않게 정하고, 후보별 토크나이저로 잘림 0%를 확인해 기록 |
| 검색 | 선정된 DB의 정확 검색 모드로 dense top-k |
| 지표 | 근거 단위 Hit@5, Hit@10, MRR(주). 문서 단위 Recall@5(보조). 색인 시간과 비용, 질의 1건 임베딩 지연(로컬 모델은 CPU 기준) |
| 판정 | 주 지표 우선, 신뢰구간 안이면 비용, 질의 지연, 운영 단순성. 상위 2개를 7단계 교차 확인 대상으로 남긴다 |

### 5. 토크나이저 선정

용도가 둘이라 따로 고른다. 선택한 토크나이저는 `common/text_tokenizer.py` 하나로 두고 Ingest와 Query가 함께 쓴다.

| 용도 | 후보 | 방법 | 판정 기준 |
|---|---|---|---|
| 청크 길이 측정 | 문자 수, tiktoken, 선정된 임베딩 모델의 토크나이저 | 같은 텍스트에 대해 단위별 길이를 재고 임베딩 토크나이저 기준과의 비율과 분산 비교. 최대 입력을 넘어 잘리는 청크 비율 계산 | 잘림 0%를 보장하면서 가장 단순한 것 |
| Sparse 검색(BM25) | 한국어: 공백, 문자 n-gram, Kiwi, Mecab-ko. 영어: 공백+소문자화, 어간 추출 추가 | 선정 DB에 sparse 벡터로 적재해 BM25 단독 Hit@5, MRR. 문서 1천 개당 토큰화 시간. Docker 이미지 설치 난이도 | 주 지표 우선, 신뢰구간 안이면 단순하고 설치 쉬운 쪽 |

### 6. Chunking 전략 선정

| 항목 | 내용 |
|---|---|
| 질문 | 어떤 분할 방식과 크기가 근거를 끊지 않으면서 검색 정확도가 가장 높은가 |
| 분할 방식 후보 | 고정 길이(겹침 포함), 재귀 분할(문단, 문장 순), 문서 구조 기반(제목 계층 단위, 길이 상한 초과 시 재귀 분할) |
| 크기와 겹침 후보 | 크기 256, 512, 1024(5단계에서 정한 단위) 중 선정 임베딩 최대 입력 이하인 것만. 겹침 0%, 15% |
| 조합 통제 | 방식 3개를 크기 512(상한이 더 작으면 상한값), 겹침 15%로 먼저 비교하고, 1위 방식만 크기와 겹침을 바꾼다. 전체 격자를 돌리지 않는다 |
| 지표 | 근거 단위 Hit@5, MRR. 근거 보존율(gold_evidence 구절이 한 청크 안에 온전히 들어간 문항 비율). 청크 수, 평균 길이. 질의당 LLM에 넣는 근거 토큰 수 |
| 판정 | Hit@5 우선, 신뢰구간 안이면 근거 보존율, 그다음 근거 토큰 수가 적은 쪽 |

근거 보존율을 따로 재는 이유: Hit@k는 구절의 일부만 걸려도 성공으로 칠 수 있다. 잘린 근거는 생성 단계에서 Hallucination이나 불완전한 답으로 이어진다.

### 7. Embedding 교차 확인

| 항목 | 내용 |
|---|---|
| 질문 | 단순 청킹으로 고른 임베딩이 확정된 Chunking에서도 여전히 낫는가 |
| 방법 | 4단계 상위 2개 모델을 6단계 확정 Chunking으로 다시 색인해 Hit@5, MRR 비교 |
| 판정 | 순위 유지면 확정. 뒤집혔는데 차이가 신뢰구간 안이면 원래 선택 유지. 신뢰구간 밖이면 임베딩을 바꾸고 6단계를 다시 실행 |

### 8. 프롬프트, 인용 파서, 거절 판정 구현과 임계값 보정

| 항목 | 내용 |
|---|---|
| 구현 | `prompt_builder`(번호 매긴 근거, `[n]` 인용 지시, 근거 부족 토큰, 문서 속 지시 무시 문구), `citation_parser`, `evidence_checker` |
| 거절 판정 기준 | 검색 방식(dense, hybrid)과 상관없이 **dense 최고 점수**로 판정한다. RRF 점수는 순위 기반이라 임계값을 둘 수 없고, Part C에서 검색 방식만 바꿨는데 거절 동작까지 바뀌면 변인이 둘이 된다 |
| 임계값 보정 | dev set 답 있음 30문항과 답 없음 8문항의 dense 최고 점수 분포를 그리고, 답 있음 문항을 잘못 거절하는 비율을 5% 이하로 묶는 값 중 답 없음 거절이 가장 많은 값을 고른다 |
| 산출물 | `research/refusal_threshold.md`(분포 그래프, 선택한 값, 오거절과 미거절 비율) |

임계값은 1차 필터다. 임계값을 넘은 답 없음 문항은 LLM의 근거 부족 토큰으로 2차 판정한다.

### 9. LLM 선정

| 항목 | 내용 |
|---|---|
| 질문 | 품질 하한을 넘는 생성 모델 중 비용이 가장 낮은 것은 무엇인가 |
| 조사 | 제공 모델 목록, 단가, 컨텍스트 길이, temperature 고정 지원(`gpt-6.1-terra`는 기본값 1만 허용), seed와 JSON 출력 지원, 스트리밍 지원 |
| 실험 | 확정된 검색 결과, 프롬프트, 임계값을 고정 입력으로 dev set 생성. 인용 형식 준수율, 존재하지 않는 인용 번호 비율, 답 없음 문항 거절률, 답 있음 문항 오거절률, 근거 밖 내용 포함 여부(수동 검토), 문항당 비용과 지연, 첫 토큰 지연 |
| 판정 | 품질 하한(인용 형식 준수율 95% 이상, 답 있음 오거절률 10% 이하)을 넘는 후보 중 최저 비용 |
| 산출물 | `research/llm_selection.md` |

Judge 모델은 Part B에서 Judge 신뢰성 측정과 함께 고른다.

### Part B 선정: Gold Set 및 Metric 정의

| 단계 | 내용 |
|---|---|
| 조사 | 기존 RAG 평가 체계(RAGAS, ARES, RAGChecker, TruLens 등)의 지표 정의와 판정 방식 조사. 채택, 변형, 미채택 항목과 이유 기록 |
| Gold Set 설계 | 유형 분포, 필드 구조, 구축 방법, dev/test 분리 규칙 확정 |
| 파일럿 | test set 10문항으로 지표 전체를 먼저 돌려 판정 불가, 모호 사례 수집 후 루브릭 수정 |
| 지표 타당성 검증 | 의도적으로 망가뜨린 시스템에서 지표가 실제로 떨어지는지 확인. 검색 결과를 무작위 청크로 바꾸면 Recall과 Faithfulness가 떨어져야 하고, 거절 로직을 끄면 Refusal Accuracy가 떨어져야 한다. 떨어지지 않는 지표는 측정하려는 것을 측정하지 못하는 것으로 보고 재설계 |
| Judge 검증 | 반복 일치율, 사람 라벨 대비 kappa(아래 Part B 절) |
| 산출물 | `research/gold_metric_selection.md`, `data/gold/dev_set.jsonl`, `data/gold/test_set.jsonl` |

## Part A: RAG QA 서비스

MVP에 한정하지 않는다. Query 경로는 실서비스 환경의 변수(동시 요청, 외부 API 지연과 실패, 크레딧 소진)를 견디는 FastAPI 서버로 만든다.

### Ingest 경로 (쓰기, 오프라인 배치)

1. Corpus 다운로드: manifest의 고정 버전 원문을 받고 sha256 검증. 해시가 같으면 다시 받지 않음
2. 정제: 원문 형식별 파싱, 마크업과 반복 요소(목차, 내비게이션) 제거, 공백 정규화, 메타데이터(doc_id, title, url, section 경로) 추출
3. 청크: Chunking 전략 실험에서 확정한 방식, 크기, 겹침으로 분할(길이는 토크나이저 실험에서 확정한 단위). chunk_id는 `sha256(doc_id, section_path, text)`
4. 임베딩: 배치 호출, 재시도와 타임아웃
5. 인덱스 저장: 벡터 DB upsert. 컬렉션 메타데이터에 임베딩 모델, 토크나이저, Chunk 설정 해시 기록

### Query 경로 (읽기, 온라인)

1. 질문 수신과 검증: `POST /v1/query`
2. 검색: 질의 임베딩 후 top-k. Part C에서 BM25 결합(hybrid)을 설정으로 전환
3. 근거 충분성 판정: dense 최고 점수가 임계값 미만이면 LLM 호출 없이 거절. hybrid 검색에서도 판정은 dense 점수로 한다
4. LLM 답변 생성: 번호 매긴 근거로 프롬프트 조립, `[n]` 인용 강제, 근거 부족 시 정해진 토큰 출력
5. Citation 반환: `[n]` 파싱, 실제 제공한 근거 번호만 남기고 출처 정보로 변환. 근거 부족 토큰이면 `insufficient_context`

Streaming(`POST /v1/query/stream`)은 정식 범위다. 같은 파이프라인을 쓰고 생성 토큰을 SSE로 흘린 뒤 마지막 이벤트로 검증된 인용 목록을 보낸다.

### API 서버 (FastAPI)

| 항목 | 내용 | 이유 |
|---|---|---|
| 비동기 처리 | async 엔드포인트, `AsyncOpenAI`, 벡터 DB async 클라이언트 | LLM 대기 중 다른 요청을 처리 |
| 수명 주기 | lifespan에서 클라이언트 생성, 인덱스 계약 검증, 종료 시 연결 정리 | 요청마다 연결을 만들지 않고, 잘못된 인덱스로 기동하지 않음 |
| 동시 LLM 호출 상한 | 세마포어로 상한, 대기 한도 초과 시 503과 `Retry-After` | 업스트림 rate limit과 크레딧 폭주 방지 |
| 타임아웃과 재시도 | 임베딩, LLM, 벡터 DB 호출마다 타임아웃. 멱등한 읽기 호출만 지수 백오프 재시도 | 느린 업스트림이 워커를 붙잡지 않게 함 |
| 에러 매핑 | 업스트림 실패 502, 업스트림 타임아웃 504, 벡터 DB 실패 503. 에러 본문에 내부 정보와 비밀값 미포함 | 클라이언트가 재시도 여부를 판단 가능 |
| 요청 추적 | `X-Request-ID` 수신 또는 생성, structlog contextvars로 모든 로그에 부착, 응답 헤더로 반환 | 한 요청의 검색, 생성, 인용 로그를 묶어 추적 |
| 접근 제어 | `API_KEY` 환경변수가 설정되면 `X-API-Key` 헤더 필수 | 인증 없이 외부에 노출되면 누구나 크레딧을 소모 |
| 상태 확인 | `GET /health`(프로세스 생존), `GET /ready`(벡터 DB 연결과 인덱스 계약 일치) | compose healthcheck와 배포 환경 readiness 분리 |
| OpenAPI | 엔드포인트마다 설명, 필드 설명, 요청 예제 | 평가자가 `/docs`에서 바로 호출 |

### Schema 초안

```
Request  { question: str(1..1000), top_k: int(1..20, 기본 5) }
Response { status: "answered" | "insufficient_context",
           answer: str,
           citations: [{ ref: int, doc_id, title, url, chunk_id, snippet }],
           meta: { model, embedding_model, retrieval_scores, dropped_citations, latency_ms, usage } }
```

### 완료 기준

- 새 환경에서 `make corpus`, `make ingest`, `docker compose up`, 질의 한 번이 README 절차대로 동작
- Ingest를 두 번 돌려도 chunk 수가 그대로
- 근거 없는 질문에 `insufficient_context` 반환
- 색인과 다른 임베딩 모델로 Query를 띄우면 기동 거부
- Streaming 응답의 마지막 이벤트 인용 목록이 비스트리밍 응답과 같은 규칙으로 검증됨
- 업스트림 타임아웃, 실패, 동시 호출 상한 초과가 각각 504, 502, 503으로 매핑됨
- 외부 API를 mock한 단위 테스트와 통합 테스트 통과
- 선정 실험 기록 일곱 건(데이터셋, 데이터베이스, Embedding, 토크나이저, Chunking, 거절 임계값, LLM)이 `research/`에 존재

## Part B: Eval Harness

### Gold Set

- 규모: dev set 38문항(선정 실험용, 구성은 선정 실험 절 참고), test set 40문항(최종 평가용, 전체 필드). 두 셋은 같은 근거 구절을 공유하는 문항이 없게 분리
- test set 유형 분포

| 유형 | 비중 | 목적 |
|---|---|---|
| 사실 추출 | 30% | 검색과 인용 정확도 |
| 다중 문서 종합, 추론 | 25% | 생성 품질 |
| 요약 | 15% | 원문 요구 "생성형 질의" |
| 답 없음(문서 밖 질문) | 20% | 응답 불가 로직, Hallucination 측정 |
| 유사 용어, 버전 혼동 같은 함정 | 10% | 사전 지식에 끌려가는 Hallucination 관찰 |

- 필드: id, split, question, type, answerable, gold_doc_ids, gold_evidence, acceptance_criteria(반드시 포함할 요점, 포함하면 안 되는 내용), origin(직접 작성, LLM 초안 후 수정)
- 구축 방법: 문서에서 LLM으로 초안 생성, 사람이 전부 검토하고 수정, 일부는 직접 작성
- 편향과 한계 기록: LLM 초안은 Chunk 경계 안에서 답이 나오는 질문으로 쏠린다. 작성자가 한 명이라 질문 문체가 단조롭다

### Metric (선정 실험 결과로 확정. 아래는 후보)

| Metric | 방식 | 선정 이유 | 맹점 |
|---|---|---|---|
| Retrieval Hit@k | 규칙 기반. top-k 청크에 gold_evidence 구절이 들어 있는지(문서 단위 Recall은 보조) | 생성 실패와 검색 실패를 분리 | 근거가 여러 구절에 흩어진 다중 문서 문항은 부분 일치 처리가 필요 |
| Faithfulness | Judge. 답변의 주장을 나누고 각 주장이 인용 근거로 뒷받침되는지 판정 | Hallucination을 직접 측정 | Judge가 근거를 잘못 읽으면 같이 틀림 |
| Answer Correctness | Judge. acceptance_criteria 충족 여부를 요점 단위로 판정 | 근거에 충실해도 질문에 답하지 못한 경우를 잡음 | 기준 작성 품질에 의존 |
| Refusal Accuracy | 규칙 기반. 답 없는 문항에서 거절, 답 있는 문항에서 응답 | 거절 로직의 과소, 과잉을 함께 봄 | 부분적으로 답할 수 있는 문항은 판정 모호 |
| Citation Precision | Judge. 인용한 chunk가 해당 문장을 실제로 뒷받침하는지 | 원문 필수 요구인 Citation의 품질 | Faithfulness와 상관이 높을 수 있음 |

검색, 생성, 거절을 각각 다른 지표로 분리해야 Part C에서 원인을 짚을 수 있다. 타당성 검증에서 떨어지지 않는 지표, 다른 지표와 거의 같은 값을 내는 지표는 제외한다.

### Judge 신뢰성 확보

- 생성 모델과 다른 계열의 Judge 모델을 써서 자기 선호 편향을 줄인다
- temperature 0, seed 고정, JSON Schema 구조화 출력, 점수 대신 요점별 이진 판정 후 집계. temperature 고정을 지원하지 않는 모델이면 3회 다수결로 판정
- 일관성: 같은 입력으로 Judge를 3회 실행해 판정 일치율 측정
- Human Alignment: 20개 답변을 사람이 같은 루브릭으로 라벨링하고 Judge와의 일치율, Cohen's kappa 보고
- Judge 프롬프트와 루브릭은 버전 파일로 두고 해시를 결과에 기록

### 자동화와 재현성

- 단일 명령: `make eval CONFIG=configs/baseline.yaml`
- 산출물: `reports/<run_id>/results.jsonl`(문항별 원시 결과), `summary.md`(지표 표, 유형별 분해)
- 기록 항목: git commit hash, corpus manifest 해시, gold set 해시, 생성과 Judge와 Embedding 모델 이름과 버전, 토크나이저, 프롬프트 해시, seed, 설정 전체
- LLM 응답 캐시: 요청 내용 해시를 키로 저장해 같은 설정 재실행 시 같은 결과와 0원 비용을 보장

### CI 연동 설계(가산, README 설계 논의만)

- PR마다 test set 일부(빠른 셋)를 캐시와 함께 실행하고 main의 기준 Report와 비교
- 지표별 허용 하락폭을 두고 초과하면 실패. 문항 수가 적으므로 bootstrap 신뢰구간으로 노이즈와 실제 하락을 구분
- main 병합 시 전체 셋 실행 후 기준 Report 갱신

## Part C: 개선 실험

### 1차 가설 후보(추천)

- 가설: Dense 단독 검색에 BM25 Sparse 검색을 RRF로 결합하면 고유명사, 설정 키, 버전 번호가 들어간 질의에서 Recall@k가 오르고, 그 결과 Answer Correctness가 오른다. Faithfulness는 유지된다
- 근거: Dense 임베딩은 의미 유사도에 강하고 정확한 토큰 일치에 약하다. 함정 유형 문항이 이 약점을 겨냥한다
- 측정: Baseline과 Hybrid를 test set, 같은 seed로 실행. 전체와 유형별 지표, paired bootstrap 95% 신뢰구간, 지연시간과 비용 함께 비교

### 예비 가설

- Chunk 크기와 겹침 변경
- 근거 충분성 판정 임계값 조정에 따른 Refusal Accuracy와 Correctness의 trade-off 곡선

### Report 구성

README의 Part C 절에 Hypothesis, Result(표와 그래프), Analysis(유형별 분해로 원인 해석, 실패 사례 인용), Next Steps.

## 일정과 Commit 단위

선정 실험은 파이프라인 모듈을 설정만 바꿔 재사용하므로, Ingest와 Query 최소 구현과 Recall@k 계산이 선정 실험보다 먼저 온다.

| 순서 | 파트 | 묶음 |
|---|---|---|
| 1 | Part A | 저장소 골격: uv, Dockerfile, compose(api, ingest 일회성), 로거, 설정 |
| 2 | Part A | 데이터셋 선정 실험, manifest, 다운로드 |
| 3 | Part A | dev set 작성(38문항) |
| 4 | Part A | Ingest 경로 최소 구현(정제, 고정 길이 Chunking, 설정으로 교체 가능), `selection_run` 골격 |
| 5 | Part A | 데이터베이스 선정 실험, 선정 DB 저장소 구현과 compose 추가 |
| 6 | Part A | Query 경로 최소 구현(검색까지), `retrieval_metric`(근거 단위 Hit@k, MRR) |
| 7 | Part A | Embedding 선정 실험 |
| 8 | Part A | 토크나이저 선정 실험 |
| 9 | Part A | Chunking 전략 선정 실험 |
| 10 | Part A | Embedding 교차 확인 |
| 11 | Part A | 프롬프트, 인용 파서, 거절 판정 구현과 임계값 보정 |
| 12 | Part A | LLM 선정 실험 |
| 13 | Part A | Query 경로 완성: Schema, 응답 변환, 인덱스 계약 검증 |
| 14 | Part A | API 서버 완성: 비동기, lifespan, 동시 호출 상한, 에러 매핑, 요청 추적, 접근 제어, health와 ready |
| 15 | Part A | Streaming(SSE) |
| 16 | Part B | Gold Set 및 Metric 조사, 파일럿, 타당성 검증 |
| 17 | Part B | test set 확정, Eval Runner, Judge Metric, Report |
| 18 | Part B | Judge 일관성과 Human Alignment 측정 |
| 19 | Part C | Hybrid 실험과 분석 |
| 20 | 문서 | README 전체, 한계와 향후 과제(증분 Ingest API 포함), CI 설계 논의 |

## 비용 추정(추정치, 모델 가격 확인 후 갱신)

- Embedding: 50~100페이지 분량은 수십만 토큰 수준. 후보 2~3개를 각각 색인해도 소액 예상
- 선정 실험: dev set 38문항 × 생성 후보 2~3개 + closed-book 검증. 수천 원 수준 예상
- 평가 1회: test set 40문항 × (생성 1회 + Judge 3종) ≈ 160회 호출
- 전체 1만~2만원 내외 예상. 캐시로 재실행 비용 제거
- GPU 인스턴스는 쓰지 않는다. 오픈소스 Embedding 후보는 CPU로 로컬 실행

## 사용자가 직접 할 일

- 엘리스AI클라우드 기관 생성 후 기관 URL을 담당자에게 이메일로 전달, 5만원 크레딧 충전 확인
- ML API 모델 라이브러리에서 생성, Judge, Embedding 후보 모델의 Serverless 엔드포인트 확인과 API Key 발급
- 후보 데이터셋 수집
- dev set, test set 검토와 Human Alignment용 사람 라벨링 20건
- 제출 기한 확인(전형 안내 이메일)

## 미확인 사항

- 엘리스 모델 라이브러리에 Embedding 모델이 Serverless로 있는지
- Judge로 쓸 수 있는 다른 계열 모델이 있는지
- 각 모델 토큰 단가
