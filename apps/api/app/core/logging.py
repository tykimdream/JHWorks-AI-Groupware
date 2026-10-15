import json
import logging
import traceback
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any, Literal

_request_id: ContextVar[str] = ContextVar("request_id", default="-")


def set_request_id(value: str) -> Token[str]:
    return _request_id.set(value)


def reset_request_id(token: Token[str]) -> None:
    _request_id.reset(token)


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id.get()
        return True


class JsonFormatter(logging.Formatter):
    _structured_fields = {
        "duration_ms": "durationMs",
        "error_code": "errorCode",
        "event": "event",
        "method": "method",
        "path": "path",
        "status_code": "statusCode",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "requestId": getattr(record, "request_id", "-"),
            "message": record.getMessage(),
        }
        for record_name, output_name in self._structured_fields.items():
            value = getattr(record, record_name, None)
            if value is not None:
                payload[output_name] = value
        if record.exc_info:
            exception_type, _, exception_traceback = record.exc_info
            payload["exception"] = {
                "type": exception_type.__name__ if exception_type else "Exception",
                "stack": [
                    f"{frame.filename}:{frame.lineno}:{frame.name}"
                    for frame in traceback.extract_tb(exception_traceback)
                ],
            }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(
    log_format: Literal["json", "text"],
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"],
) -> None:
    handler = logging.StreamHandler()
    handler.addFilter(RequestContextFilter())
    if log_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(levelname)s request_id=%(request_id)s logger=%(name)s %(message)s"
            )
        )
    logging.basicConfig(level=log_level, handlers=[handler], force=True)
