"""X-API-Key 검사 의존성. API_KEY가 설정된 경우에만 켜진다."""
import hmac
from typing import Annotated
from fastapi import Depends, Header, HTTPException

from app.api.query_runtime import QueryRuntime, get_runtime


def require_api_key(
    runtime: Annotated[QueryRuntime, Depends(get_runtime)],
    x_api_key: Annotated[str | None, Header(description="API_KEY가 설정된 서버에서만 필수")] = None,
) -> None:
    """키 비교는 길이와 내용에 따라 시간이 달라지지 않게 compare_digest로 한다."""
    expected = runtime.settings.api_key
    if expected is None:
        return
    if x_api_key is None or not hmac.compare_digest(x_api_key.encode(), expected.get_secret_value().encode()):
        raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")
