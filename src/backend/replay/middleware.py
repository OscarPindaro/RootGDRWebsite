"""Recorder for the backend calls of a session.

Recording is switched on with ``POST /api/replay/start`` (``harness replay
start``, or the toggle in the user menu): a typed JSON config is written to
disk, so every worker sees the same session and filters without process-local
state. While it is on, each JSON request the app answers is appended to
``harness-artifacts/replay/backend/<session>.json`` together with its response
body (size-capped), and ``harness replay export --mode backend`` turns that
file into an integration test.

Pure ASGI rather than ``BaseHTTPMiddleware``: the request and response bodies
have to be read and handed on unchanged, which is the one thing the base class
makes awkward.
"""

from __future__ import annotations

import json
from pathlib import Path

from .anonymize import Anonymizer, IDENTITY_PATHS
from .schemas import BackendStep, RecordingConfig

RECORDINGS = Path("harness-artifacts/replay")
CONFIG = RECORDINGS / ".recording.json"
SKIP_PREFIXES = ("/static", "/api/replay")
READ_ONLY_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
# Response bodies larger than this are not recorded: replays need ids and
# small payloads, not downloaded files or bulk exports.
MAX_RESPONSE_BYTES = 64 * 1024


def recording_config() -> RecordingConfig | None:
    """The worker-shared recording config, or ``None`` when recording is off."""
    if not CONFIG.is_file():
        return None
    return RecordingConfig.model_validate_json(CONFIG.read_text(encoding="utf-8"))


def start(config: RecordingConfig) -> None:
    RECORDINGS.mkdir(parents=True, exist_ok=True)
    _write_config(config)


def stop() -> None:
    CONFIG.unlink(missing_ok=True)


def _write_config(config: RecordingConfig) -> None:
    RECORDINGS.mkdir(parents=True, exist_ok=True)
    temporary = CONFIG.with_suffix(".tmp")
    temporary.write_text(config.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(CONFIG)


def _json(payload: bytes, content_type: str) -> object | None:
    if not payload or "application/json" not in content_type:
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


class ReplayMiddleware:
    """Record every JSON request/response while a recording is active."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        config = recording_config()
        path = scope.get("path", "")
        method = scope.get("method", "GET").upper()
        excluded = SKIP_PREFIXES + tuple(config.exclude if config else ())
        if (
            config is None
            or path.startswith(excluded)
            or (config.read_only and method not in READ_ONLY_METHODS)
        ):
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

        step = BackendStep(
            method=method,
            path=path,
            query=(scope.get("query_string") or b"").decode("latin-1") or None,
            body=_json(payload, _header(scope.get("headers"), b"content-type")),
            status=captured.get("status", 0),
            response=_json(
                captured["body"] if isinstance(captured["body"], bytes) else b"",
                str(captured["content_type"]),
            ),
        )
        _append(config, step)


def _header(raw_headers, name: bytes) -> str:
    for key, value in raw_headers or []:
        if key.lower() == name:
            return value.decode("latin-1")
    return ""


def _append(config: RecordingConfig, step: BackendStep) -> None:
    """Anonymize one step and append it to the session file."""
    anonymizer = Anonymizer(config.aliases)
    identity_path = step.path.startswith(IDENTITY_PATHS)
    step.body = anonymizer.scrub(step.body, identity_path=identity_path)
    step.response = anonymizer.scrub(step.response, identity_path=identity_path)
    config.aliases = anonymizer.aliases
    _write_config(config)

    directory = RECORDINGS / "backend"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{config.session}.json"
    existing = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
    existing.append(step.model_dump(exclude_none=True))
    path.write_text(
        json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
