"""외부 의존(벡터 DB, LLM)의 실패를 층 사이에 전달하는 예외. API 층이 이 종류만 보고 HTTP 상태를 정한다."""


class UpstreamError(Exception):
    """외부 의존 실패의 공통 부모. 메시지에는 내부 주소나 비밀값을 넣지 않는다."""


class VectorStoreError(UpstreamError):
    """벡터 DB 연결 실패나 오류 응답."""


class LlmTimeoutError(UpstreamError):
    """LLM 호출이 타임아웃(재시도 포함)으로 끝났다."""


class LlmFailureError(UpstreamError):
    """LLM 호출이 연결 실패나 오류 응답(재시도 소진)으로 끝났다."""


class LlmBusyError(UpstreamError):
    """LLM 동시 호출 상한에서 대기 한도를 넘겼다."""
