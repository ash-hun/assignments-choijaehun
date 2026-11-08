# 개발 원칙(dev_principle)

이 프로젝트는 처음부터 `dev_principle`이라는 개발 원칙을 따라 만들었다. 원칙의 정본은 저장소 밖(작성자의 Claude Code 스킬)에 있어서, 이 문서에 이 프로젝트에서 실제로 적용한 규칙을 정리한다. 저장소 루트의 `CLAUDE.md`에 같은 원칙의 요약 카드가 있다.

## 핵심 명제

**같은 입력이면 같은 결과가 나와야 한다.** 세 가지 방법으로 지킨다.

| 축 | 뜻 | 이 프로젝트에서 |
|---|---|---|
| 최소 | 짓지 않은 코드가 가장 재현 가능하다 | 아직 오지 않은 요구를 위한 코드, 쓰이지 않는 설정과 추상화를 만들지 않는다 |
| 수렴 | 지은 것은 두 번 실행해도 같은 상태로 간다 | 다시 실행하는 것이 곧 복구다. 컬렉션은 지우고 다시 만들거나 upsert하고, 결과 파일은 매번 전부 덮어쓴다 |
| 투영 | 문서는 코드에서 유도한다 | 문서에 생성 시각이나 버전 번호를 넣지 않는다. 코드가 그대로면 문서를 다시 써도 diff가 없다 |

## 진행 순서

큰 그림에서 세부로 내려간다. 순서를 거꾸로 밟으면 먼저 만든 모듈이 나중에 정한 기능 정의와 맞지 않아 버려진다.

1. **기획과 기능 정의**: 서비스가 하는 일, 기능 목록, 기능별 입력과 결과, 범위 밖을 정한다. 결과물은 `docs/features.md` 초안이다.
2. **아키텍처 설계**: 층 구조, 디렉토리 트리, 기능별 모듈과 파이프라인, 상태 저장 위치, 외부 연동을 정한다. 결과물은 `project_planning/architecture.md`다.
3. **하위 모듈 구현**: 모듈을 만들고 단위 테스트를 붙인 뒤, 파이프라인으로 엮어 통합 테스트를 붙인다.

1, 2단계는 결과를 보여주고 승인을 받은 뒤 다음으로 넘어간다. 구현 중에는 라이브러리나 파일 배치처럼 갈리는 지점을 묻지 않고 가장 그럴듯한 쪽으로 끝까지 간 뒤, 끝에 "A로 갔고 이유는 B, 바꾸려면 C" 형식으로 모아 보고한다. 삭제, 권한 변경, 외부 배포처럼 되돌리기 어려운 실행은 먼저 확인받는다.

## 짓기 전에 확인하는 순서

처음 성립하는 칸에서 멈춘다.

1. 애초에 필요한가? 아직 오지 않은 요구를 위한 것이면 만들지 않는다.
2. 이미 이 코드베이스에 있나? 있으면 쓴다. 같은 일을 하는 코드가 둘이면 정본이 둘이 된다.
3. 표준 라이브러리나 이미 설치된 의존성으로 되나?
4. 플랫폼 기능(DB 제약, 벡터 DB 내장 기능)으로 되나?
5. 그때서야 동작하는 최소 구현을 만든다.

예: BM25의 IDF는 직접 계산하지 않고 Qdrant의 `Modifier.IDF`에 맡겼다. 청크 길이는 tiktoken을 새로 들이지 않고 fastembed가 이미 쓰는 `tokenizers`로 센다.

## 코드 규칙

### 층과 의존 방향

디렉토리 이름이 층을, 파일 이름이 대상과 역할을 말한다. import 경로만 읽고 모듈의 역할을 알 수 있어야 한다.

| 층 | 역할 | 이 프로젝트의 예 |
|---|---|---|
| `api` | HTTP 요청 해석과 응답 변환 | Query 경로 FastAPI 라우터 |
| `cli` | 배치와 실험 진입점(조립만 한다) | `chunking_selection_cli.py`, `corpus_cli.py` |
| `service` | 업무 규칙과 흐름. `ingest`, `query`, `eval`로 나눈다 | `service/ingest/chunk_splitter.py`, `service/eval/retrieval_metric.py` |
| `agent` | LangGraph 그래프와 노드(필요할 때만) | 없음 |
| `repository` | 저장소 접근 | `qdrant_chunk_repository.py` |
| `client` | 외부 시스템, 모델 연동 | `embedding_client.py`, `llm_client.py` |
| `schema` | 데이터 모델 | `chunk_schema.py`, `gold_schema.py` |
| `common` | 모든 층이 쓰는 공통 모듈 | `logger.py`, `settings.py`, `text_tokenizer.py` |

의존은 위에서 아래로만 흐른다. `repository`와 `client`는 위 층을 import하지 않고, `common`은 어떤 층도 import하지 않는다. 순환을 피하려고 함수 안에 넣은 import도 역방향 의존으로 본다.

### 이름

- 파일 이름은 `<대상>_<역할>.py`이고, 클래스 이름은 파일 이름과 맞춘다(`text_tokenizer.py`에는 `TextTokenizer`, `chunk_splitter.py`에는 `ChunkSplitter`).
- `utils.py`, `helpers.py`, `misc.py`, `manager.py`, `handler.py`처럼 역할을 말하지 않는 이름은 쓰지 않는다.
- 같은 대상은 모든 층에서 같은 낱말로 부른다(`chunk_splitter`, `chunk_repository`, `chunk_schema`).

### import 순서

두 그룹으로 나눈다. 외부(표준 라이브러리와 서드파티)는 줄 길이 오름차순, 한 줄 띄고, 로컬은 줄 길이 내림차순이다. 정렬 규칙이 하나로 고정돼 있어야 import 블록의 diff가 의미 있는 변경만 담는다.

```python
import sys
import json
import asyncio
from qdrant_client import AsyncQdrantClient

from app.repository.qdrant_chunk_repository import QdrantChunkRepository
from app.client.embedding_client import EmbeddingClient
from app.common.logger import get_logger
```

쓰지 않는 import, 와일드카드 import, 습관적인 `from __future__ import annotations`는 넣지 않는다.

### 함수와 클래스

- **함수 하나는 결정 하나, 또는 부수효과 하나.** 계산과 I/O를 섞지 않는다. 예: `evidence_preservation`, `pick_best`는 순수 함수이고, 색인과 검색은 `ChunkingBenchmark`가 맡는다.
- **상태나 의존이 있으면 기능 단위 클래스로 묶고 생성자로 주입한다.** 예: `ChunkSplitter`는 토큰 수 함수와 토큰 위치 함수를 생성자로 받아, 테스트에서는 단어 단위 가짜 함수로 바꿔 끼운다.
- **추상 클래스(`ABC`, 몸통 없는 `Protocol`)는 쓰지 않는다.** 공통 동작은 실제로 동작하는 구체 클래스에 둔다. 상속 깊이는 1~2다.
- 상태도 의존도 없는 순수 변환은 함수로 둔다.

### 타입, docstring, 주석

- 모든 함수와 메서드의 인자와 반환값에 타입 힌트를 붙인다. `-> None`도 생략하지 않는다. `uv run mypy`(strict)가 오류 0이어야 한다.
- 구조가 정해진 dict는 pydantic 모델로 바꾼다.
- 모든 `.py` 첫머리에 이 모듈이 프로젝트에서 무엇인지 최대 2줄 docstring을 쓴다. 2줄로 안 담기면 파일이 두 가지 일을 하고 있다는 신호다.
- 모듈 상수는 import 직후에 모은다.
- 주석은 왜(why)만 쓴다. 코드가 이미 말하는 것을 다시 적지 않는다.

### 마커

의도적으로 감수한 한계는 코드에 표시한다. 표시하지 않은 의도는 버그와 구분되지 않는다.

- `# ponytail: <한계>, <업그레이드 조건>`: 알려진 한계를 감수한 단순화. 예: fastembed 내부 속성에 기대는 토크나이저 접근
- `# idempotent: <이유>, <해결 방법>`: 의도적인 비멱등

## 멱등성

모든 층에서 같은 네 가지를 지킨다.

1. **무엇이 같은 것인지 먼저 정한다.** 다시 실행해도 변하지 않는 값을 자연 키로 쓴다. 자동 증가 ID와 생성 시각은 후보가 아니다. 예: `chunk_id`는 (문서 경로, 청크 내용)의 sha256이고, Gold 문항 id는 (split, 유형, 순번)에서 계산한 uuid5다.
2. **상태를 만들지 말고 맞춘다.** `create_x()` 대신 `ensure_x()`, `exist_ok=True`, upsert를 쓴다.
3. **어디서 죽어도 다시 실행하면 되게 한다.** 예: 선정 실험은 시작할 때 컬렉션을 지우고 새로 만들며, 결과 파일을 매번 전부 덮어쓴다.
4. **확인과 변경 사이의 틈을 없앤다.** 코드의 중복 검사는 편의이고, 실제 보장은 저장소의 유니크 키가 한다.

결정 로직 안에서 `uuid4()`, `datetime.now()`, `random`을 부르지 않는다. 무작위가 필요하면 seed를 고정한다(bootstrap seed 2026, 원문 표집 seed 2026).

## 도구와 환경

| 용도 | 도구 | 이 프로젝트에서 |
|---|---|---|
| 패키지 관리 | uv | `pyproject.toml`과 `uv.lock`을 커밋한다. 의존성 그룹은 `dev`(테스트, 타입 검사)와 `korean`(형태소 분석기, 실험 전용) |
| 실행 환경 | Docker, Docker Compose | 앱, 벡터 DB, 실험을 모두 `compose.yaml` 서비스로 띄운다. `make <대상>`이 `docker compose run --rm --build`를 감싼다 |
| 테스트 | pytest | `uv run pytest`, `make test` |
| 정적 검사 | mypy | `uv run mypy`(strict), `make typecheck` |

pip, poetry, conda, 손으로 만든 venv는 쓰지 않는다. 이미지 태그에 `latest`를 쓰지 않고 버전을 고정한다.

## 로깅

- 로거는 `app/common/logger.py`의 structlog 커스텀 로거 하나만 쓴다. 각 모듈은 `logger = get_logger(__name__)` 한 줄로 받는다.
- 개발 환경은 rich 콘솔 출력, 운영 환경은 `LOG_FORMAT=json`이다.
- `print`, `logging.basicConfig`, 모듈마다 따로 만든 핸들러는 쓰지 않는다.
- 비밀값과 개인정보는 로그에 남기지 않는다. 마스킹 프로세서가 마지막 방어선이다.

## 에이전트

에이전트를 만든다면 LangGraph로만 구현한다. Deepagents와 다른 에이전트 프레임워크는 쓰지 않는다. 상태는 타입으로 선언하고, LLM과 도구는 생성자로 주입하며, `recursion_limit`과 호출 타임아웃을 항상 건다.

## 테스트

| 종류 | 파일 이름 | 대상 | 예 |
|---|---|---|---|
| 단위 | `tests/unit/test_{기능명}_{모듈명}.py` | 기능을 구현하는 모듈 하나 | `test_ingest_chunk_splitter.py`, `test_selection_run_retrieval_metric.py` |
| 통합 | `tests/integ/test_{기능명}.py` | 여러 모듈을 엮은 기능 파이프라인 | |

- **외부 API는 항상 mock으로 대체한다.** 실제 네트워크로 나가는 테스트는 쓰지 않는다.
- 많이 쓰지 않는다. 분기와 변환이 있는 모듈만 단위 테스트를 갖고, 공개 함수마다 정상 경로 하나와 가장 중요한 실패나 경계 하나를 둔다.
- 테스트 안에는 주석을 거의 쓰지 않는다. 테스트 함수 이름이 무엇을 보장하는지 말한다.

## 문서

| 파일 | 내용 | 언제 있나 |
|---|---|---|
| `docs/features.md` | 기능 목록, 기능별 설명, 기능을 구현하는 파일과 테스트 매칭 | 항상 |
| `docs/api_spec.md` | API 명세. 엔드포인트마다 다시 호출하면 어떻게 되는지 포함 | API가 있으면 |
| `docs/view_spec.md` | 화면 정의. 빈 상태와 에러 상태 포함 | 화면이 있을 때만 |

작업할 때마다 그 작업 안에서 갱신한다. 나중으로 미루면 하지 않게 된다.

## 보안

신뢰 경계를 넘는 모든 입력과 출력에 적용한다.

- **입력 검증**: 요청 본문과 파라미터는 pydantic 모델로 받고 길이, 범위, 형식을 제한한다.
- **XSS**: 출력은 자동 이스케이프에 맡긴다. `dangerouslySetInnerHTML`, Jinja2 `|safe`는 쓰지 않는다.
- **인젝션**: SQL은 파라미터 바인딩만 쓴다. `subprocess`는 리스트 인자로 넘기고 `shell=True`를 쓰지 않는다. 외부 입력에 `eval`, `exec`, `pickle.loads`를 쓰지 않는다.
- **비밀값**: 코드와 저장소에 두지 않는다. 환경변수(`.env`, git 제외)에서 읽어 `SecretStr`로 다루고, 없으면 기동 시점에 실패한다. 커밋 전에 키와 엔드포인트 주소가 섞이지 않았는지 검사한다.
- **외부 호출**: 타임아웃을 항상 건다. 사용자가 준 URL을 서버가 호출하면 허용 목록으로 제한한다.
- **LLM 출력과 검색 문서**: 신뢰하지 않는 입력으로 다룬다. 문서 안의 지시는 따르지 않는다(프롬프트 인젝션 방어).

## 작업마다 점검하는 네 가지

작업을 끝내기 전에 점검하고 결과를 보고에 한 줄씩 남긴다. 점검하지 않은 항목을 이상 없다고 쓰지 않는다.

| 항목 | 보는 것 |
|---|---|
| API 부하 | 요청당 외부 호출과 DB 쿼리 수, 반복문 안의 호출, 재시도 폭주, LLM 호출 횟수와 토큰 |
| 자원 점유 | 메모리에 통째로 올리는 데이터, 닫히지 않는 연결, async 경로 안의 블로킹 호출 |
| 보안 | 이번 변경이 새로 연 신뢰 경계 |
| 구조 효율 | 역방향 의존, 같은 일을 하는 코드의 중복, 기능과 파일 매핑이 `features.md`와 맞는지 |

## 끝내기 전 확인

1. 지금 한 번 더 실행하면 어떻게 되는지 말로 답할 수 있는가?
2. 손댄 모든 `.py`가 docstring, 타입 힌트, import 순서, 파일 이름 규칙을 지키는가?
3. 마지막 수정 이후에 `uv run pytest`와 `uv run mypy`를 돌렸는가?
4. `features.md`와 해당 문서를 이번 변경에 맞춰 고쳤는가?
5. 점검 네 가지 결과를 적었는가?
6. 검증한 것과 검증하지 않은 것을 나눠서 보고했는가? 돌려본 것만 확인했다고 쓴다.

## 이 프로젝트에서 더한 작업 절차

원칙 위에 다음 절차를 더해 진행했다.

- **단계마다 브랜치를 따로 만든다.** 예: `part-a/embedding-selection`, `part-a/tokenizer-selection`, `part-a/chunking-selection`. push한 뒤 PR을 열고, 병합은 작성자가 직접 한다.
- **커밋 메시지는 커밋 전에 검수받는다.** 접두어 `init:`, `feat:`, `data:`를 쓰고 본문은 한국어로 쓴다. 코드 변경(`feat:`)과 실험 결과(`data:`)는 커밋을 나눈다.
- **선정 실험은 판정 규칙을 실험 전에 정한다.** 결과를 본 뒤 규칙을 바꾸면 그 이유를 실험 기록의 "계획과 달라진 점"에 남긴다.
