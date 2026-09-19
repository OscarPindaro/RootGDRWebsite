"""Request-scoped correlation context.

Values live in ``ContextVar``s so they are per-request and are reset when the
request ends; nothing is process-global. Inbound ``X-Request-ID`` /
``X-Workflow-ID`` / W3C ``traceparent`` values are accepted when valid, and
missing request/trace/span values are generated. The JSON log formatter reads
the same variables, so every line carries OpenTelemetry-compatible correlation
fields.
"""

from __future__ import annotations

import contextvars
import re
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

_HEX32 = re.compile(r"^[0-9a-f]{32}$")
_HEX16 = re.compile(r"^[0-9a-f]{16}$")
_TRACEPARENT = re.compile(
    r"^(?P<version>[0-9a-f]{2})-(?P<trace>[0-9a-f]{32})-(?P<span>[0-9a-f]{16})-(?P<flags>[0-9a-f]{2})$"
)

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)
trace_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "trace_id", default=None
)
span_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "span_id", default=None
)
workflow_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "workflow_id", default=None
)
user_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "user_id", default=None
)
world_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "world_id", default=None
)


def new_trace_id() -> str:
    return uuid.uuid4().hex


def new_span_id() -> str:
    return uuid.uuid4().hex[:16]


def valid_trace_id(value: str | None) -> str | None:
    if value and _HEX32.match(value) and value != "0" * 32:
        return value
    return None


def valid_span_id(value: str | None) -> str | None:
    if value and _HEX16.match(value) and value != "0" * 16:
        return value
    return None


def parse_traceparent(value: str | None) -> tuple[str | None, str | None]:
    """Return ``(trace_id, span_id)`` from a W3C ``traceparent`` header.

    Invalid or all-zero identifiers are ignored rather than trusted, and the
    caller generates replacements.
    """
    if not value:
        return None, None
    match = _TRACEPARENT.match(value.strip().lower())
    if match is None:
        return None, None
    return (
        valid_trace_id(match.group("trace")),
        valid_span_id(match.group("span")),
    )


@dataclass
class Correlation:
    request_id: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    workflow_id: str | None = None
    user_id: str | None = None
    world_id: str | None = None

    def as_dict(self) -> dict[str, str]:
        return {
            key: value
            for key, value in {
                "request_id": self.request_id,
                "trace_id": self.trace_id,
                "span_id": self.span_id,
                "workflow_id": self.workflow_id,
                "user_id": self.user_id,
                "world_id": self.world_id,
            }.items()
            if value
        }


def current() -> Correlation:
    return Correlation(
        request_id=request_id_var.get(),
        trace_id=trace_id_var.get(),
        span_id=span_id_var.get(),
        workflow_id=workflow_id_var.get(),
        user_id=user_id_var.get(),
        world_id=world_id_var.get(),
    )


@contextmanager
def bind(correlation: Correlation) -> Iterator[Correlation]:
    """Bind correlation values for the duration of a request, then reset.

    Every variable is set (even to ``None``) so a token exists for each, and
    values assigned later in the request (user id, world id) are discarded when
    the request ends. A request can never leak its identifiers into the next
    one on the same task.
    """
    values = [
        (request_id_var, correlation.request_id),
        (trace_id_var, correlation.trace_id),
        (span_id_var, correlation.span_id),
        (workflow_id_var, correlation.workflow_id),
        (user_id_var, correlation.user_id),
        (world_id_var, correlation.world_id),
    ]
    tokens = [(var, var.set(value)) for var, value in values]
    try:
        yield correlation
    finally:
        for var, token in reversed(tokens):
            var.reset(token)


def set_user_id(user_id: str | None) -> None:
    user_id_var.set(user_id)


def set_world_id(world_id: str | None) -> None:
    world_id_var.set(world_id)


def resolve(
    *,
    request_id: str | None = None,
    workflow_id: str | None = None,
    traceparent: str | None = None,
) -> Correlation:
    """Build a correlation, accepting valid inbound values and filling gaps."""
    trace_id, span_id = parse_traceparent(traceparent)
    return Correlation(
        request_id=(request_id or "").strip() or uuid.uuid4().hex,
        trace_id=trace_id or new_trace_id(),
        span_id=span_id or new_span_id(),
        workflow_id=(workflow_id or "").strip() or None,
    )
