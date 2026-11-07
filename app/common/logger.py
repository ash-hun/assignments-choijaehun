"""프로젝트 전체가 쓰는 structlog 로거를 설정하고 돌려주는 공통 모듈. 어떤 층도 import 하지 않는다."""
import os
import sys
import logging
import structlog
from typing import Any
from collections.abc import MutableMapping
from structlog.dev import RichTracebackFormatter
from structlog.tracebacks import ExceptionDictTransformer

DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FORMAT = "console"
REDACTED = "***"
SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "password",
        "token",
        "access_token",
        "refresh_token",
        "authorization",
        "api_key",
        "cookie",
        "set-cookie",
        "secret",
    }
)

_configured: bool = False


def _mask(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: REDACTED if str(k).lower() in SENSITIVE_KEYS else _mask(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(_mask(v) for v in value)
    return value


def _redact(_: Any, __: str, event_dict: MutableMapping[str, Any]) -> MutableMapping[str, Any]:
    for key in list(event_dict):
        event_dict[key] = REDACTED if key.lower() in SENSITIVE_KEYS else _mask(event_dict[key])
    return event_dict


def configure_logging(level: str | None = None, fmt: str | None = None) -> None:
    """루트 로거와 structlog 를 한 번만 설정한다. 다시 불려도 핸들러가 늘지 않는다."""
    global _configured
    if _configured:
        return

    level_name = (level or os.environ.get("LOG_LEVEL") or DEFAULT_LOG_LEVEL).upper()
    fmt_name = (fmt or os.environ.get("LOG_FORMAT") or DEFAULT_LOG_FORMAT).lower()

    shared: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _redact,
    ]
    # 트레이스백에 지역 변수를 싣지 않는다. 비밀값이 로그로 새는 가장 흔한 경로다.
    renderer: list[Any] = (
        [
            structlog.processors.ExceptionRenderer(ExceptionDictTransformer(show_locals=False)),
            structlog.processors.JSONRenderer(),
        ]
        if fmt_name == "json"
        else [structlog.dev.ConsoleRenderer(exception_formatter=RichTracebackFormatter(show_locals=False))]
    )

    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # uvicorn, httpx 같은 표준 logging 로그도 같은 형식과 마스킹을 거치게 한다.
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared,
            processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, *renderer],
        )
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level_name)
    _configured = True


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """name 의 로거를 돌려준다. 설정 전이면 먼저 설정한다."""
    configure_logging()
    logger: structlog.stdlib.BoundLogger = structlog.stdlib.get_logger(name)
    return logger
