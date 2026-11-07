# Gold Set 데이터

선정 실험과 평가에 쓰는 질의, 정답, 근거 데이터. 한 줄에 문항 하나인 JSONL이다. 모델 정의는 `app/schema/gold_schema.py`의 `GoldItem`이고, 이 문서는 그 정의를 옮긴 것이다. 정의가 바뀌면 이 문서도 함께 고친다.

## 파일

| 파일 | 내용 | 쓰는 곳 |
|---|---|---|
| `dev_set.jsonl` | dev set 정본, 영어 38문항 | 선정 실험(DB, Embedding, 토크나이저, Chunking, 거절 임계값, LLM) |
| `dev_set_ko.jsonl` | dev set 한국어 번역 묶음 38문항. 행마다 `dev_set.jsonl`의 한 행과 짝 | 한국어 질의 성능 측정 |
| `drafts/dev_draft.jsonl` | dev set LLM 초안(검수 전) | 정본과 비교용. 평가에 쓰지 않음 |
| `drafts/dev_ko_draft.jsonl` | 한국어 번역 초안(검수 전) | 같음 |
| `test_set.jsonl` | test set 정본(미작성) | 최종 평가 |

정본 파일은 검수를 거쳐서만 바뀐다. `make gold-draft`, `make gold-translate`는 `drafts/`만 덮어쓴다. 구축 방법, 검수 내역, 한계는 `research/dev_set_construction.md`에 있다.

## 한 행의 스키마

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `id` | string (UUID) | 예 | 문항 식별자. 아래 "id 규칙" 참고 |
| `split` | `"dev"` \| `"test"` | 예 | 문항이 속한 묶음 |
| `type` | `"factual"` \| `"multi_doc"` \| `"summary"` \| `"trap"` \| `"unanswerable"` | 예 | 문항 유형. 아래 "문항 유형" 참고 |
| `question` | string | 예 | 질문. 1~1000자 |
| `answerable` | boolean | 예 | 문서에 답이 있는지 |
| `reference_answer` | string | 예 | 짧은 정답. 답 없는 문항은 빈 문자열. 번역 묶음에서도 원문(영어) 정답을 그대로 둔다 |
| `evidence` | array of `GoldEvidence` | 예 | 정답 근거 구절 목록. 답 없는 문항은 빈 배열 |
| `evidence[].doc_id` | string | 예 | Corpus 기준 상대 경로. 예: `concepts/cache.md` |
| `evidence[].quote` | string | 예 | 그 문서에 글자 그대로 있는 구간(줄바꿈 포함 원문 그대로) |
| `acceptance_criteria` | array of string \| null | 아니오 | 반드시 포함할 요점, 포함하면 안 되는 내용. test set에서만 채운다. dev set은 `null` |
| `origin` | `"llm_draft"` \| `"llm_draft_reviewed"` \| `"human_written"` | 예 | 작성 출처. LLM 초안은 사람 검토를 마친 뒤에만 `llm_draft_reviewed`가 된다 |
| `notes` | string \| null | 아니오 | 검수 메모. 답 없는 문항은 답이 없는 이유 |
| `language` | `"en"` \| `"ko"` | 아니오(기본 `"en"`) | 질문 언어 |
| `translation_of` | string (UUID) \| null | 아니오 | 번역 행이 가리키는 원문 행의 `id`. 원문 행은 `null` |

근거 문서 목록(`gold_doc_ids`)은 파일에 저장하지 않고 `evidence[].doc_id`에서 순서를 지켜 중복을 뺀 값으로 계산한다.

## 문항 유형

| 유형 | 뜻 | 근거 |
|---|---|---|
| `factual` | 한 곳에 적힌 구체적 사실(값, 이름, 기본값, 동작) | 1개 |
| `multi_doc` | 서로 링크된 두 문서의 정보를 합쳐야 답할 수 있음 | 문서마다 1개 이상 |
| `summary` | 문서나 큰 절의 요점 정리. 정답은 요점 3~5개 | 3~5개 |
| `trap` | 버전별 차이, preview/experimental 기능, 폐기 항목, 정확한 식별자(플래그, 환경변수, 설정 키)에 정답이 걸려 있어 낡은 사전 지식으로 틀리기 쉬움 | 1~2개 |
| `unanswerable` | 문서에 답이 없음. 근접 주제 문항(비슷한 구절이 있어 오답을 유도)과 먼 주제 문항을 섞음 | 없음 |

## 지켜야 하는 규칙

`make gold-check SPLIT=dev LANG_CODE=en|ko`가 아래를 검사하고, 어기면 종료 코드 1로 끝난다.

| 규칙 | 검사 위치 |
|---|---|
| 모든 필드가 위 타입과 제약을 따른다 | 스키마 |
| `answerable`이 `true`면 `evidence`가 1개 이상, `false`면 빈 배열 | 스키마 |
| `type`이 `unanswerable`인 것과 `answerable`이 `false`인 것이 일치 | 스키마 |
| `language`가 `en`이 아니면 `translation_of`가 있고, `en`이면 없다 | 스키마 |
| 파일 안에서 `id`가 중복되지 않는다 | gold-check |
| `evidence[].quote`가 `doc_id` 문서에 글자 그대로 있다 | gold-check |
| 번역 행의 `translation_of`가 원문 파일에 있고, `type`, `evidence`, `reference_answer`가 원문 행과 같다 | gold-check(번역 묶음) |
| 원문 파일의 모든 행에 번역 행이 있다 | gold-check(번역 묶음) |

## id 규칙

무작위 UUID(`uuid4`)는 쓰지 않는다. 초안을 다시 만들 때마다 id가 바뀌면 사람 라벨, 평가 결과, Judge 결과와의 연결이 끊기기 때문이다.

| 행 | 계산 |
|---|---|
| 원문 행 | `uuid5(GOLD_ID_NAMESPACE, "<split>-<type>-<유형 안 순번 2자리>")`. 예: `dev-factual-01` |
| 번역 행 | `uuid5(GOLD_ID_NAMESPACE, "<원문 행 id>:<language>")` |

`GOLD_ID_NAMESPACE = uuid5(NAMESPACE_URL, "elice-rag-qa/gold")`. 질문 문장을 고쳐도 id는 바뀌지 않는다.

## 예시

원문 행:

```json
{
  "id": "19721d33-1604-5726-b355-948eddb4aa48",
  "split": "dev",
  "type": "factual",
  "question": "Where does uv keep credentials saved with `uv auth` on Unix by default, and is that file meant to be edited by hand?",
  "answerable": true,
  "reference_answer": "In a plaintext file in uv's state directory, e.g. `~/.local/share/uv/credentials/credentials.toml`; it is not intended to be edited manually.",
  "evidence": [
    {
      "doc_id": "concepts/authentication/http.md",
      "quote": "Credentials are stored in a plaintext file in uv's state directory, e.g.,\n`~/.local/share/uv/credentials/credentials.toml` on Unix. This file is currently not intended to be\nedited manually."
    }
  ],
  "acceptance_criteria": null,
  "origin": "llm_draft",
  "notes": "검수 중 교체. ...",
  "language": "en",
  "translation_of": null
}
```

같은 문항의 번역 행은 `id`, `question`, `language`, `translation_of`만 다르다.

```json
{
  "id": "<uuid5(원문 id + ':ko')>",
  "question": "Unix에서 uv는 `uv auth`로 저장한 인증 정보를 기본적으로 어디에 보관하나요? 그리고 그 파일을 직접 편집해도 되나요?",
  "language": "ko",
  "translation_of": "19721d33-1604-5726-b355-948eddb4aa48"
}
```

답 없는 문항:

```json
{
  "type": "unanswerable",
  "question": "What is uv's default timeout for HTTP requests to package indexes, and which environment variable changes it?",
  "answerable": false,
  "reference_answer": "",
  "evidence": [],
  "notes": "근접 주제 문항. 문서에는 캐시 잠금 대기 시간만 있고 HTTP 요청 시간 제한은 없음. ..."
}
```

## 만드는 방법

```
make gold-draft SPLIT=dev           # 영어 초안 → drafts/dev_draft.jsonl
# 검수 후 dev_set.jsonl 작성 (research/dev_set_construction.md에 기록)
make gold-check SPLIT=dev LANG_CODE=en
make gold-translate SPLIT=dev       # 한국어 번역 초안 → drafts/dev_ko_draft.jsonl
# 검수 후 dev_set_ko.jsonl 작성
make gold-check SPLIT=dev LANG_CODE=ko
```
