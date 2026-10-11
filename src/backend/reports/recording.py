"""The recording of one report's reproduction.

The development recorder is the opposite of this: one instance-wide session,
switched on by an admin, written to the replay folder. A reproduction belongs to
a single report, is started by the reader, and has to survive ordinary
navigation — a full page load cannot carry a custom header, so the browser is
joined to its recording by a cookie and the steps live beside the report's own
evidence, under the configured storage root.

Every recorded backend step carries the request and trace ids of the call, so a
submitted report can point at the exact call instead of a time window.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, ValidationError

from ..correlation import current
from ..filesystem.base import FileSystem
from ..log import get_logger

logger = get_logger(__name__)

COOKIE = "report_reproduction"
FRONTEND = "frontend"
BACKEND = "backend"
# The report's own API is never recorded: an evidence upload would put a
# screenshot in the recording, and the panel's own writes are not the incident.
SKIP_PREFIXES = ("/api/reports", "/static", "/api/replay")
MAX_STEPS = 2_000
# Response bodies larger than this are not recorded: a reproduction needs ids
# and small payloads, not a downloaded file.
MAX_RESPONSE_BYTES = 64 * 1024
_LOCATION = "reports/{report}/recording"


class ReproductionConfig(BaseModel):
    """Worker-shared state of one active reproduction, written as JSON."""

    report_id: str
    frontend_session: str
    backend_session: str
    started_at: str
    active: bool = True


def _location(report_id: uuid.UUID) -> str:
    return _LOCATION.format(report=report_id)


def config_path(report_id: uuid.UUID) -> str:
    return f"{_location(report_id)}/config.json"


def steps_path(report_id: uuid.UUID, side: str) -> str:
    return f"{_location(report_id)}/{side}.json"


def report_from_cookie(scope: dict) -> uuid.UUID | None:
    """The report a request belongs to, from the reproduction cookie.

    The value is parsed as a UUID rather than trusted as a path: it becomes a
    directory name, and a malformed one must not reach the filesystem.
    """
    for key, value in scope.get("headers") or []:
        if key.lower() != b"cookie":
            continue
        for pair in value.decode("latin-1").split(";"):
            name, _, raw = pair.strip().partition("=")
            if name != COOKIE:
                continue
            try:
                return uuid.UUID(raw)
            except ValueError:
                return None
    return None


async def read_config(
    filesystem: FileSystem, report_id: uuid.UUID
) -> ReproductionConfig | None:
    try:
        payload = await filesystem.read_async(config_path(report_id))
    except OSError:
        return None
    try:
        return ReproductionConfig.model_validate(json.loads(payload))
    except ValueError:
        logger.warning("A reproduction config is unreadable", report_id=str(report_id))
        return None


async def start(filesystem: FileSystem, report_id: uuid.UUID) -> ReproductionConfig:
    """Open one reproduction, replacing any previous attempt for this report."""
    config = ReproductionConfig(
        report_id=str(report_id),
        frontend_session="f" + uuid.uuid4().hex[:16],
        backend_session="b" + uuid.uuid4().hex[:16],
        started_at=datetime.now(UTC).isoformat(),
    )
    await _write(filesystem, config_path(report_id), config.model_dump())
    await _write(filesystem, steps_path(report_id, FRONTEND), [])
    await _write(filesystem, steps_path(report_id, BACKEND), [])
    return config


async def stop(filesystem: FileSystem, report_id: uuid.UUID) -> None:
    config = await read_config(filesystem, report_id)
    if config is None:
        return
    config.active = False
    await _write(filesystem, config_path(report_id), config.model_dump())


async def append_steps(
    filesystem: FileSystem,
    report_id: uuid.UUID,
    side: str,
    steps: list[dict],
) -> int:
    """Append steps to one side of the recording and return the total."""
    if not steps:
        return len(await load_steps(filesystem, report_id, side))
    stored = await load_steps(filesystem, report_id, side)
    stored.extend(steps)
    if len(stored) > MAX_STEPS:
        # A reproduction is a bounded window, not an always-on recorder.
        stored = stored[-MAX_STEPS:]
    await _write(filesystem, steps_path(report_id, side), stored)
    return len(stored)


async def load_steps(
    filesystem: FileSystem, report_id: uuid.UUID, side: str
) -> list[dict]:
    try:
        payload = await filesystem.read_async(steps_path(report_id, side))
    except OSError:
        return []
    try:
        stored = json.loads(payload)
    except ValueError:
        return []
    return stored if isinstance(stored, list) else []


async def _write(filesystem: FileSystem, path: str, payload: object) -> None:
    await filesystem.write_async(
        path, json.dumps(payload, ensure_ascii=False, default=str).encode()
    )


def backend_step(
    *,
    method: str,
    path: str,
    query: str | None,
    body: object,
    status: int,
    response: object,
) -> dict:
    """One backend call, joined to the browser side by request and trace ids."""
    correlation = current()
    return {
        "method": method,
        "path": path,
        "query": query,
        "body": body,
        "status": status,
        "response": response,
        "request_id": correlation.request_id,
        "trace_id": correlation.trace_id,
        "at": datetime.now(UTC).isoformat(),
    }


def _header(raw_headers, name: bytes) -> str:
    for key, value in raw_headers or []:
        if key.lower() == name:
            return value.decode("latin-1")
    return ""


def _json(payload: bytes, content_type: str) -> object | None:
    if not payload or "application/json" not in content_type:
        return None
    try:
        return json.loads(payload)
    except ValueError:
        return None


class ReportRecorderMiddleware:
    """Record the backend calls of an active report reproduction.

    Pure ASGI rather than ``BaseHTTPMiddleware``, like the development recorder
    and for the same reason: the request and the response bodies have to be read
    and handed on unchanged.
    """

    def __init__(self, app, filesystem: FileSystem) -> None:
        self.app = app
        self.filesystem = filesystem

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        report_id = report_from_cookie(scope)
        path = scope.get("path", "")
        if report_id is None or path.startswith(SKIP_PREFIXES):
            await self.app(scope, receive, send)
            return
        config = await read_config(self.filesystem, report_id)
        if config is None or not config.active:
            await self.app(scope, receive, send)
            return

        payload = b""
        more = True
        while more:
            message = await receive()
            payload += message.get("body", b"")
            more = message.get("more_body", False)

        async def replay_receive() -> dict:
            return {"type": "http.request", "body": payload, "more_body": False}

        captured: dict[str, object] = {"body": b"", "content_type": ""}

        async def capture_send(message: dict) -> None:
            if message["type"] == "http.response.start":
                captured["status"] = message["status"]
                captured["content_type"] = _header(
                    message.get("headers"), b"content-type"
                )
            elif message["type"] == "http.response.body":
                body = captured["body"]
                if isinstance(body, bytes) and len(body) < MAX_RESPONSE_BYTES:
                    captured["body"] = body + message.get("body", b"")
            await send(message)

        await self.app(scope, replay_receive, capture_send)

        step = backend_step(
            method=scope.get("method", "GET").upper(),
            path=path,
            query=(scope.get("query_string") or b"").decode("latin-1") or None,
            body=_json(payload, _header(scope.get("headers"), b"content-type")),
            status=int(captured.get("status") or 0),
            response=_json(
                captured["body"] if isinstance(captured["body"], bytes) else b"",
                str(captured["content_type"]),
            ),
        )
        try:
            await append_steps(self.filesystem, report_id, BACKEND, [step])
        except OSError, ValidationError:
            # Recording never breaks the request it is recording.
            logger.warning("A step could not be stored", report_id=str(report_id))
