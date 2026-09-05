"""Application-wide logging setup with structured context.

Called once from ``create_app`` so every module's ``get_logger(__name__)``
inherits the same handlers and level — no per-module configuration needed.

Console handler only for now. File logging (rotation, multi-worker safety)
is a separate concern — when needed, prefer delegating to external tools
(``logrotate``, Docker log drivers, systemd journal) rather than in-process
handlers like ``RotatingFileHandler`` which corrupt when multiple workers
rotate simultaneously.

Uvicorn's own access logs are left untouched (it configures its own loggers).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi.encoders import jsonable_encoder

from .config import LoggingConfig

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE_FORMAT = "%d-%m-%Y %H:%M:%S"
_CONTEXT_ATTR = "structured_context"


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
            extra[_CONTEXT_ATTR] = {**extra.get(_CONTEXT_ATTR, {}), **context}
        super()._log(level, msg, args, exc_info, extra, stack_info, stacklevel + 1)


class TextFormatter(logging.Formatter):
    """Human-readable formatter that appends JSON-encoded structured context."""

    def format(self, record: logging.LogRecord) -> str:
        rendered = super().format(record)
        context = getattr(record, _CONTEXT_ATTR, None)
        if not context:
            return rendered
        return f"{rendered} {json.dumps(jsonable_encoder(context), default=str)}"


class JsonFormatter(logging.Formatter):
    """JSON formatter for log collectors while retaining standard logger calls."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, datefmt=_DATE_FORMAT),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        context = getattr(record, _CONTEXT_ATTR, None)
        if context:
            payload["context"] = context
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(jsonable_encoder(payload), default=str)


def get_logger(name: str) -> StructuredLogger:
    """Return an application logger that accepts keyword context."""
    return logging.getLogger(name)  # type: ignore[return-value]


def setup_logging(config: LoggingConfig) -> None:
    """Configure the root logger's single console handler."""
    level = getattr(logging, config.level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)

    for handler in list(root.handlers):
        if getattr(handler, "_app_handler", False):
            root.removeHandler(handler)

    formatter: logging.Formatter
    if config.format == "json":
        formatter = JsonFormatter()
    else:
        formatter = TextFormatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(formatter)
    console._app_handler = True  # type: ignore[attr-defined]
    root.addHandler(console)

    for noisy in ("httpx", "httpcore", "watchfiles"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


logging.setLoggerClass(StructuredLogger)
