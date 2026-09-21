"""Application-wide logging setup with structured, censored context.

Called once from ``create_app`` so every module's ``get_logger(__name__)``
inherits the same handlers and level — no per-module configuration needed.

Console handler only. File logging (rotation, multi-worker safety) is a
separate concern — when needed, prefer delegating to external tools
(``logrotate``, Docker log drivers, systemd journal) rather than in-process
handlers like ``RotatingFileHandler`` which corrupt when multiple workers
rotate simultaneously.

Every record is redacted recursively before it is formatted: ``SecretStr``
values, email addresses, field names that are sensitive by convention
(password, token, secret, authorization, ...) and fields explicitly marked
sensitive on a ``LogModel``.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, ClassVar

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, SecretStr
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from . import correlation
from .config import LoggingConfig

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE_FORMAT = "%d-%m-%Y %H:%M:%S"
_CONTEXT_ATTR = "structured_context"
_MASK = "***"
_EMAIL = re.compile(r"^([^@\s]+)@([^@\s]+\.[^@\s]+)$")

# Field names whose value is always sensitive, wherever it appears.
_SENSITIVE_NAMES = {
    "password",
    "passwd",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "jwt",
    "jwt_secret",
    "authorization",
    "api_key",
    "apikey",
    "cookie",
    "session",
}


class LogModel(BaseModel):
    """Base for structured domain values passed to the logger.

    ``extra="forbid"`` keeps the shape explicit. Mark a field sensitive with
    ``Field(json_schema_extra={"sensitive": True})`` and it is masked even if
    its name is not in the convention list.
    """

    model_config = ConfigDict(extra="forbid")

    _sensitive_fields: ClassVar[set[str]] = set()


def _mask_secret(value: SecretStr) -> str:
    raw = value.get_secret_value()
    return f"****{raw[-4:]}" if raw else _MASK


def _mask_email(value: str) -> str:
    match = _EMAIL.match(value)
    if match is None:
        return value
    local, domain = match.groups()
    return f"{local[0]}{_MASK}@{domain}"


def _field_is_sensitive(field: Any) -> bool:
    extra = field.json_schema_extra
    return bool(isinstance(extra, dict) and extra.get("sensitive"))


def redact(value: Any, *, key: str | None = None) -> Any:
    """Recursively censor secrets, emails and sensitive fields."""
    if key is not None and key.lower() in _SENSITIVE_NAMES:
        return _MASK
    if isinstance(value, SecretStr):
        return _mask_secret(value)
    if isinstance(value, BaseModel):
        values = value.model_dump()
        return {
            name: _MASK
            if _field_is_sensitive(field) or name.lower() in _SENSITIVE_NAMES
            else redact(values[name], key=name)
            for name, field in type(value).model_fields.items()
        }
    if isinstance(value, dict):
        return {str(k): redact(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return _mask_email(value)
    return value


class StructuredLogger(logging.Logger):
    """Logger accepting arbitrary keyword arguments as structured context."""

    def _log(
        self,
        level: int,
        msg: object,
        args: Any,
        exc_info: Any = None,
        extra: dict[str, Any] | None = None,
        stack_info: bool = False,
        stacklevel: int = 1,
        **context: Any,
    ) -> None:
        extra = dict(extra or {})
        if context:
            redacted = redact(context)
            assert isinstance(redacted, dict)
            extra[_CONTEXT_ATTR] = {**extra.get(_CONTEXT_ATTR, {}), **redacted}
        super()._log(level, msg, args, exc_info, extra, stack_info, stacklevel + 1)


class TextFormatter(logging.Formatter):
    """Human-readable formatter that appends JSON-encoded structured context."""

    def format(self, record: logging.LogRecord) -> str:
        rendered = super().format(record)
        context = record.__dict__.get(_CONTEXT_ATTR)
        if not context:
            return rendered
        return f"{rendered} {json.dumps(jsonable_encoder(context), default=str)}"


class JsonFormatter(logging.Formatter):
    """JSON formatter with OpenTelemetry-compatible correlation fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, datefmt=_DATE_FORMAT),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Correlation identifiers sit at the top level so log collectors can
        # index them without knowing the context shape.
        payload.update(correlation.current().as_dict())
        context = record.__dict__.get(_CONTEXT_ATTR)
        if context:
            payload["context"] = context
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(jsonable_encoder(payload), default=str)


def get_logger(name: str) -> StructuredLogger:
    """Return an application logger that accepts keyword context."""
    return logging.getLogger(name)  # type: ignore[return-value]


class AppStreamHandler(logging.StreamHandler):
    pass


def setup_logging(config: LoggingConfig) -> None:
    """Configure the root logger's single console handler."""
    level = logging.getLevelNamesMapping().get(config.level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)

    for handler in list(root.handlers):
        if isinstance(handler, AppStreamHandler):
            root.removeHandler(handler)

    formatter: logging.Formatter
    if config.format == "json":
        formatter = JsonFormatter()
    else:
        formatter = TextFormatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    console = AppStreamHandler()
    console.setLevel(level)
    console.setFormatter(formatter)
    root.addHandler(console)

    for noisy in ("httpx", "httpcore", "watchfiles"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Bind per-request correlation and return the request id in the response.

    Accepts valid inbound ``X-Request-ID`` / ``X-Workflow-ID`` / W3C
    ``traceparent`` values and generates anything missing. The context is
    reset when the request ends, so nothing leaks into the next request.
    """

    async def dispatch(self, request: Request, call_next):
        resolved = correlation.resolve(
            request_id=request.headers.get("X-Request-ID"),
            workflow_id=request.headers.get("X-Workflow-ID"),
            traceparent=request.headers.get("traceparent"),
        )
        with correlation.bind(resolved):
            response = await call_next(request)
            assert resolved.request_id is not None
            response.headers["X-Request-ID"] = resolved.request_id
            return response


logging.setLoggerClass(StructuredLogger)
