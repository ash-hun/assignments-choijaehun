"""원문, 텍스트, 설정의 sha256을 계산하는 공통 모듈. 재실행 시 같은 입력인지 판정하는 기준이다."""
import hashlib


def sha256_bytes(data: bytes) -> str:
    """바이트열의 sha256 16진수 문자열을 돌려준다."""
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    """UTF-8로 인코딩한 텍스트의 sha256을 돌려준다."""
    return sha256_bytes(text.encode("utf-8"))
