"""Unit tests for backend replay recording filters."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.replay import middleware
from backend.replay.schemas import RecordingConfig


@pytest.fixture
def recording_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_path = tmp_path / ".recording.json"
    monkeypatch.setattr(middleware, "RECORDINGS", tmp_path)
    monkeypatch.setattr(middleware, "CONFIG", config_path)
    return config_path


async def _request_that_must_not_read_body(config: RecordingConfig, path: str) -> bool:
    middleware.start(config)
    called = False

    async def app(scope, receive, send) -> None:
        nonlocal called
        called = True

    async def receive() -> dict:
        raise AssertionError("filtered requests must not read their body")

    async def send(message: dict) -> None:
        pass

    await middleware.ReplayMiddleware(app)(
        {"type": "http", "path": path, "method": "POST"}, receive, send
    )
    return called


def test_recording_config_is_stored_as_typed_json(recording_path: Path) -> None:
    expected = RecordingConfig(
        session="b123", read_only=True, exclude=["/health", "/metrics"]
    )

    middleware.start(expected)

    assert recording_path.read_text(encoding="utf-8").startswith("{")
    assert middleware.recording_config() == expected


async def test_excluded_path_is_filtered_before_reading_body(
    recording_path: Path,
) -> None:
    config = RecordingConfig(session="b123", exclude=["/api/private"])

    assert await _request_that_must_not_read_body(config, "/api/private/items")


async def test_read_only_recording_filters_writes_before_reading_body(
    recording_path: Path,
) -> None:
    config = RecordingConfig(session="b123", read_only=True)

    assert await _request_that_must_not_read_body(config, "/api/worlds")


@pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS"])
async def test_read_only_recording_keeps_safe_methods(
    recording_path: Path, method: str
) -> None:
    middleware.start(RecordingConfig(session=method.lower(), read_only=True))

    async def app(scope, receive, send) -> None:
        await receive()
        await send({"type": "http.response.start", "status": 200})

    async def receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict) -> None:
        pass

    await middleware.ReplayMiddleware(app)(
        {"type": "http", "path": "/health", "method": method}, receive, send
    )

    path = recording_path.parent / "backend" / f"{method.lower()}.json"
    assert json.loads(path.read_text(encoding="utf-8")) == [
        {"method": method, "path": "/health", "status": 200}
    ]
