"""Unit tests for backend replay recording: filters, bodies, anonymization."""

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


async def _record(
    recording_path: Path,
    *,
    path: str = "/api/worlds",
    request_body: bytes = b"",
    response_body: bytes = b"",
) -> list[dict]:
    middleware.start(RecordingConfig(session="btest"))

    async def app(scope, receive, send) -> None:
        await receive()
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send({"type": "http.response.body", "body": response_body})

    async def receive() -> dict:
        return {"type": "http.request", "body": request_body, "more_body": False}

    async def send(message: dict) -> None:
        pass

    await middleware.ReplayMiddleware(app)(
        {
            "type": "http",
            "path": path,
            "method": "POST",
            "headers": [(b"content-type", b"application/json")],
        },
        receive,
        send,
    )
    return json.loads(
        (recording_path.parent / "backend" / "btest.json").read_text(encoding="utf-8")
    )


async def test_response_body_is_recorded(recording_path: Path) -> None:
    steps = await _record(
        recording_path,
        request_body=b'{"name": "Boschetto"}',
        response_body=b'{"id": "abc", "name": "Boschetto"}',
    )

    assert steps[0]["response"] == {"id": "abc", "name": "Boschetto"}


async def test_oversized_response_body_is_not_recorded(
    recording_path: Path,
) -> None:
    steps = await _record(
        recording_path,
        response_body=b"x" * (middleware.MAX_RESPONSE_BYTES + 1),
    )

    assert "response" not in steps[0]


async def test_identities_are_anonymized_deterministically(
    recording_path: Path,
) -> None:
    steps = await _record(
        recording_path,
        path="/api/admin/users",
        request_body=json.dumps({"name": "Mario", "email": "mario@rossi.it"}).encode(),
        response_body=json.dumps(
            {"email": "mario@rossi.it", "name": "Mario", "world": "Boschetto"}
        ).encode(),
    )

    assert steps[0]["body"] == {"name": "Utente 1", "email": "user-1@example.test"}
    assert steps[0]["response"]["email"] == "user-1@example.test"
    assert steps[0]["response"]["name"] == "Utente 1"
    # Content that is not an identity is kept.
    assert steps[0]["response"]["world"] == "Boschetto"
    # The mapping lives in the worker-shared config, never in the recording.
    assert "Mario" not in json.dumps(steps)
    config = middleware.recording_config()
    assert config is not None and "Mario" in config.aliases


async def test_content_names_outside_identity_paths_are_kept(
    recording_path: Path,
) -> None:
    steps = await _record(
        recording_path,
        path="/api/worlds",
        request_body=b'{"name": "Boschetto"}',
        response_body=b'{"id": "abc", "name": "Boschetto"}',
    )

    assert steps[0]["body"] == {"name": "Boschetto"}
    assert steps[0]["response"]["name"] == "Boschetto"
