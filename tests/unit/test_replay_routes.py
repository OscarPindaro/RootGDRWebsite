"""Unit tests for the replay route guards and the anonymization of UI steps."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.auth.dependencies import get_current_admin_user, get_current_user
from backend.replay import middleware, routes
from backend.users.schemas import User


def _user(role: str) -> User:
    return User(
        id="01a0c41e-201e-74a3-93d6-0e29017a4e01",
        name="Admin",
        email="admin@example.com",
        role=role,
    )


@pytest.fixture
def recordings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "replay"
    monkeypatch.setattr(middleware, "RECORDINGS", directory)
    monkeypatch.setattr(middleware, "CONFIG", directory / ".recording.json")
    monkeypatch.setattr(routes, "RECORDINGS", directory)
    return directory


@pytest.fixture
def client(recordings: Path) -> TestClient:
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app)


def _login_as(client: TestClient, role: str) -> None:
    user = User(id="01a0c41e-201e-74a3-93d6-0e29017a4e01", name="Admin", email="admin@example.com", role=role)
    client.app.dependency_overrides[get_current_user] = lambda: user
    client.app.dependency_overrides[get_current_admin_user] = lambda: user


def test_start_and_stop_require_an_admin(recordings: Path) -> None:
    app = FastAPI()
    app.include_router(routes.router)
    client = TestClient(app)
    member = User(
        id="01a0c41e-201e-74a3-93d6-0e29017a4e01",
        name="Member",
        email="member@example.com",
        role="member",
    )
    app.dependency_overrides[get_current_admin_user] = lambda: member

    assert client.post("/api/replay/start").status_code == 403
    assert client.post("/api/replay/stop").status_code == 403


def test_start_creates_the_recording_config(
    client: TestClient, recordings: Path
) -> None:
    _login_as(client, role="admin")

    response = client.post("/api/replay/start", json={"read_only": False})

    assert response.status_code == 200
    session = response.json()["session"]
    assert (recordings / ".recording.json").is_file()
    assert session.startswith("b")


def test_browser_steps_are_anonymized_before_being_written(
    client: TestClient, recordings: Path
) -> None:
    _login_as(client, role="member")

    response = client.post(
        "/api/replay",
        json={
            "session": "s123",
            "steps": [
                {
                    "kind": "fill",
                    "selector": "[name=email]",
                    "value": "mario@rossi.it",
                    "label": "email",
                }
            ],
        },
    )

    assert response.status_code == 204
    steps = json.loads(
        (recordings / "s123.json").read_text(encoding="utf-8")
    )
    assert steps[0]["value"] == "user-1@example.test"
    # The pseudonym mapping is stored next to the recording, not inside it.
    assert "mario@rossi.it" not in json.dumps(steps)
    aliases = json.loads(
        (recordings / ".aliases" / "s123.json").read_text(encoding="utf-8")
    )
    assert aliases == {"mario@rossi.it": "user-1@example.test"}
