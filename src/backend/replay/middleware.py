"""Dev-only middleware that records the backend calls of a session.

Recording is switched on with ``POST /api/dev/replay/start`` (``harness replay
start``): the session id is written to a flag file, so every worker sees it and
no process-local state is involved. While it is on, each JSON request the app
answers is appended to ``harness-artifacts/replay/backend/<session>.json``, and
``harness replay export --mode backend`` turns that file into an httpx test.

Pure ASGI rather than ``BaseHTTPMiddleware``: the body has to be read and handed
on unchanged, which is the one thing the base class makes awkward.
"""

from __future__ import annotations

import json
from pathlib import Path

from .schemas import BackendStep

RECORDINGS = Path("harness-artifacts/replay")
FLAG = RECORDINGS / ".recording"
SKIP_PREFIXES = ("/static", "/api/dev/replay")


def recording_session() -> str | None:
    """The session being recorded, or ``None`` when recording is off."""
    if not FLAG.is_file():
        return None
    session = FLAG.read_text(encoding="utf-8").strip()
    return session or None


def start(session: str) -> None:
    RECORDINGS.mkdir(parents=True, exist_ok=True)
    FLAG.write_text(session, encoding="utf-8")


def stop() -> None:
    FLAG.unlink(missing_ok=True)


def _body(payload: bytes, content_type: str) -> object | None:
    if not payload or "application/json" not in content_type:
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


def _append(session: str, step: BackendStep) -> None:
    directory = RECORDINGS / "backend"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{session}.json"
    existing = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
    existing.append(step.model_dump(exclude_none=True))
    path.write_text(
        json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


class ReplayMiddleware:
    """Record every JSON request/response while a recording is active."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        session = recording_session()
        path = scope.get("path", "")
        if session is None or path.startswith(SKIP_PREFIXES):
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

        captured: dict[str, int] = {}

        async def capture_send(message: dict) -> None:
            if message["type"] == "http.response.start":
                captured["status"] = message["status"]
            await send(message)

        await self.app(scope, replay_receive, capture_send)

        headers = dict(scope.get("headers") or [])
        content_type = headers.get(b"content-type", b"").decode("latin-1")
        step = BackendStep(
            method=scope.get("method", "GET"),
            path=path,
            query=(scope.get("query_string") or b"").decode("latin-1") or None,
            body=_body(payload, content_type),
            status=captured.get("status", 0),
        )
        _append(session, step)
