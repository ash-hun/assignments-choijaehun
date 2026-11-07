# 데이터베이스 선정

상태: 확정(**Qdrant, gRPC 연결**).

## 질문

이 서비스의 기능 요구를 만족하면서 운영과 구현이 가장 단순한 벡터 DB는 무엇인가.

## 후보

| 후보 | 이미지(버전 고정) | Python 클라이언트 |
|---|---|---|
| Qdrant | `qdrant/qdrant:v1.20.0` | `qdrant-client` 1.20 (`AsyncQdrantClient`) |
| PostgreSQL + pgvector | `pgvector/pgvector:0.8.6-pg17` | `psycopg` 3.3 (`AsyncConnection`) + `pgvector` 0.5 |
| Chroma | `chromadb/chroma:1.5.9` | `chromadb-client` 1.5.9 (`AsyncHttpClient`) |

이미지는 2주 이상 지난 안정 버전으로 골랐다. 세 DB 모두 compose 내부 네트워크에만 두고 포트를 열지 않았다.

## 고정한 변인

| 변인 | 값 |
|---|---|
| Corpus | `uv_docs` 81개 문서, Ingest 최소 구현으로 정제 |
| 청크 | 고정 길이 1,000자, 겹침 없음, 공백 경계에서 자름. 587개 |
| 벡터 | 임시 임베딩 `BAAI/bge-small-en-v1.5`(fastembed, 384차원, L2 정규화). 1024, 1536차원은 같은 벡터를 seed 7의 가우시안 무작위 투영으로 옮김 |
| sparse 벡터 | 기능 검사용 임시 인코더. 소문자 단어를 crc32로 해시(2^20 공간), 값은 단어 빈도 |
| 질의 | dev set 38문항(영어) |
| top_k | 10 |
| 머신 | 같은 노트북(Docker Desktop, linux/aarch64). 후보를 하나씩 순서대로 측정 |

임시 임베딩을 써도 되는 이유: 이 실험은 검색 품질이 아니라 기능, 지연, 자원, 근사 검색 오차를 본다. 이 값들은 벡터의 의미보다 개수와 차원에 좌우된다. 투영은 무작위 벡터와 달리 실제 임베딩의 이웃 관계를 대체로 유지한다.

## 방법

`make db-bench`가 후보 DB를 띄우고 아래를 차원(384, 1024, 1536)마다 잰다. 결과는 `research/artifacts/database/results.json`.

1. 컬렉션을 지우고 만든 뒤 587개를 upsert(적재 시간), 같은 것을 한 번 더 upsert(재적재 시간)
2. 기능 검사 6가지를 실제 호출로 판정
3. dev set 38문항을 5개로 예열한 뒤 3회 반복(114회) dense 검색 지연
4. 같은 질의의 top-10을 numpy 전수 비교 top-10과 비교해 ANN 재현율 계산
5. 측정 전후 `docker stats`로 메모리 기록

## 결과: 기능 검사

| 기능 | 왜 필요한가 | Qdrant | pgvector | Chroma |
|---|---|---|---|---|
| 자연 키 upsert | Ingest 재실행 시 같은 상태로 수렴 | 통과 | 통과 | 통과 |
| 컬렉션 metadata(인덱스 계약) | Query 기동 시 임베딩 모델, 토크나이저 대조 | 통과(컬렉션 metadata) | 통과(별도 테이블) | 통과(컬렉션 metadata) |
| metadata 필터 | 문서 단위 검색, 디버깅 | 통과 | 통과 | 통과 |
| 클라이언트 sparse 벡터 | 토크나이저 선정 결과를 그대로 쓰는 BM25 | 통과(IDF 가중을 서버가 계산) | 통과(IDF 없음, 클라이언트가 계산해야 함) | **실패**: "Sparse vector indexing is not enabled in local" |
| dense + sparse 결합 검색 | Part C Hybrid 가설 | 통과(서버 내장 RRF) | 통과(SQL로 RRF 직접 작성) | **실패**(sparse 미지원) |
| 정확 검색 모드 | Embedding 선정에서 ANN 오차 제거 | 통과(`exact=True`) | 통과(인덱스 스캔 끄기) | **실패**(전수 비교 모드 없음) |

Chroma는 1.5 클라이언트에 sparse 인덱스와 RRF 검색 API가 있지만, 오픈소스 로컬 서버가 sparse 인덱스 생성을 거부한다(Chroma Cloud 전용 기능으로 보임, 추정). 문서만 읽었다면 통과로 판정했을 항목이라 실제 호출로 확인한 의미가 있었다.

## 결과: 성능

Qdrant는 gRPC 연결 기준이다(아래 "Qdrant 연결 방식" 참고).

| 차원 | 지표 | Qdrant | pgvector | Chroma |
|---|---|---|---|---|
| 384 | 적재(587개) | 0.05초 | 0.36초 | 0.38초 |
| 384 | 지연 p50 / p95 | 0.49 / 0.57ms | 0.36 / 0.40ms | 1.92 / 2.19ms |
| 384 | ANN 재현율@10 | 1.0000 | 0.9974 | 1.0000 |
| 1024 | 적재 | 0.09초 | 0.74초 | 0.42초 |
| 1024 | 지연 p50 / p95 | 0.70 / 1.34ms | 0.73 / 1.26ms | 1.99 / 3.98ms |
| 1024 | ANN 재현율@10 | 1.0000 | 1.0000 | 1.0000 |
| 1536 | 적재 | 0.09초 | 1.04초 | 0.44초 |
| 1536 | 지연 p50 / p95 | 0.56 / 2.32ms | 0.38 / 0.96ms | 2.26 / 4.45ms |
| 1536 | ANN 재현율@10 | 1.0000 | 1.0000 | 1.0000 |
| 전체 | 메모리(적재 전 → 적재 후, 2회 측정 범위) | 216MiB~1.07GiB → 282~417MiB | 18~49MiB → 57~80MiB | 10~12MiB → 67~73MiB |

해석:

- **지연과 적재 시간은 결정 요인이 아니다.** 세 후보 모두 p95가 5ms 이하이고 적재가 1초 남짓이다. LLM 생성(초 단위)에 비하면 무시할 수준이다. 실험 전 예상과 같다.
- **재현율 1.0은 근사 검색의 성능이 아니다.** Qdrant는 포인트가 10,000개 미만이면 HNSW 인덱스를 만들지 않고 전수 비교한다(`indexed_vectors_count` 0으로 확인). Chroma도 같은 이유로 1.0일 가능성이 높다(추정). pgvector만 처음부터 HNSW를 만들어 384차원에서 0.9974가 나왔다. 이 규모에서는 모든 후보가 사실상 정확 검색이다.
- **메모리는 Qdrant가 가장 크다.** 다만 Qdrant는 측정마다 값이 크게 흔들렸다(적재 전 216MiB와 1.07GiB). 초기화 중인 메모리가 섞였을 수 있어 범위로만 보고한다.

## Qdrant 연결 방식

처음 측정에서 Qdrant의 REST 연결 지연이 차원과 무관하게 46ms로 일정했다. 차원이 4배가 되어도 그대로라 검색 연산이 아닌 통신 계층 문제로 보고 따로 진단했다(`research/artifacts/database/qdrant_transport_probe.py`).

| 연결 | 같은 저장소 코드의 검색 지연 p50 |
|---|---|
| REST(httpx, HTTP/1.1) | 45.35ms |
| gRPC | 0.42ms |

- 같은 REST 연결이라도 응답에 payload가 어떻게 실리는지에 따라 0.7ms와 45ms를 오갔다. 응답 크기와 TCP 지연 확인 응답이 맞물리는 현상으로 보이지만 근본 원인은 확정하지 못했다(추정).
- Qdrant는 고성능 연결로 gRPC를 제공하므로 측정과 이후 구현은 gRPC로 한다. REST로 잰 첫 결과는 `results_qdrant_rest.json`에 남겼다.
- 교훈: 수치가 변인(차원)에 반응하지 않으면 측정 대상이 아니라 측정 경로를 의심한다.

## 판정

사전에 정한 순서(기능 통과, ANN 재현율 0.99 이상, 운영 단순성, 지연)를 따랐다.

1. **기능**: Chroma는 sparse 벡터, 결합 검색, 정확 검색에서 탈락했다. Part C의 Hybrid 가설과 Embedding 선정의 정확 검색이 이 기능을 쓴다.
2. **ANN 재현율**: Qdrant 1.0, pgvector 0.9974 이상으로 둘 다 통과.
3. **운영과 구현의 단순성**:

| 항목 | Qdrant | pgvector |
|---|---|---|
| 구성 요소 | 컨테이너 1개 | 컨테이너 1개 |
| BM25의 IDF | 서버가 계산(`Modifier.IDF`) | 클라이언트가 문서 빈도를 관리해야 함. Corpus가 바뀌면 다시 계산 |
| 결합 검색 | 질의 하나(`prefetch` + `FusionQuery(RRF)`) | RRF를 SQL로 직접 작성 |
| 스키마 관리 | 컬렉션 생성 호출 하나 | 확장, 테이블, 인덱스, 계약 테이블 DDL |
| 주의점 | REST 지연 문제로 gRPC 사용 필요, 메모리 큼 | 없음 |

**결정: Qdrant.** 기능을 모두 통과했고, Part C에서 쓸 BM25 IDF와 RRF 결합 검색을 서버가 제공한다. pgvector로 같은 기능을 만들려면 IDF 통계 관리와 RRF SQL을 직접 유지해야 한다. 성능 차이는 이 규모에서 의미가 없다.

감수하는 점: 메모리 사용량이 세 후보 중 가장 크고, REST 연결에서 지연 문제가 관찰돼 gRPC 연결을 강제해야 한다.

기각한 후보:

- pgvector: 기능은 모두 통과했다. 이미 Postgres를 운영하는 환경이라면 좋은 선택이다. 이 과제에서는 IDF와 결합 검색을 직접 구현하는 부담이 더 크다.
- Chroma: 오픈소스 로컬 서버가 sparse 인덱스와 정확 검색을 지원하지 않는다.

## 한계

- 587개 청크 규모의 결과다. 수십만 청크에서는 HNSW 파라미터, 메모리, 적재 시간 차이가 커질 수 있다.
- 지연은 같은 노트북, 같은 Docker 네트워크에서 쟀다. 원격 배포 환경의 네트워크 지연은 포함되지 않는다.
- 메모리 측정은 `docker stats` 1회 스냅샷이라 흔들림이 크다.
- sparse 검사는 임시 해시 인코더로 했다. 실제 BM25 품질은 토크나이저 선정 실험에서 본다.

## 재현

```
make db-bench   # 후보 DB 기동, 측정, 메모리 기록, DB 정지
```

결과: `research/artifacts/database/`(`results.json`, `results_qdrant_rest.json`, `docker_stats_idle.jsonl`, `docker_stats_loaded.jsonl`, `qdrant_transport_probe.py`).
