"""Creazione personaggio da browser — replays the requests it answered.

Flusso reale: login, crea mondo, crea personaggio draft, autosave di nome/titolo/tinta/animale, pubblicazione, letture.

Recorded session: b260921183020.
Ids created during the session are captured from the responses and
reused, so the test runs on any database. Ids that predate the session
are listed as preconditions below.

"""

from __future__ import annotations

import re
import uuid

import pytest

from src.backend.auth.dependencies import get_current_user, get_optional_user
from src.backend.db.enums import UserRole
from src.backend.dependencies import get_db_session
from src.backend.users.models import UserModel
from src.backend.users.schemas import User

pytestmark = pytest.mark.integration


async def _replay_user(db_manager) -> User:
    session = db_manager.async_session_maker()
    async with session.begin():
        model = UserModel(
            name="Replay",
            email=f"replay-{uuid.uuid4()}@example.com",
            role=UserRole.ADMIN,
        )
        session.add(model)
        await session.flush()
        user = User.model_validate(model)
    await session.close()
    return user


def _replay_id(response) -> str:
    try:
        identifier = response.json().get("id")
    except Exception:
        identifier = None
    if identifier:
        return identifier
    location = response.headers.get("hx-redirect") or response.headers.get(
        "location", ""
    )
    matches = re.findall(r"[0-9a-f-]{36}", location)
    assert matches, f"create response carries no id: {response.status_code} {location}"
    return matches[-1]


_UUID = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}"
    r"-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}"
)
_TIMESTAMP = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?$"
)


_ACTORS = ("owner", "createdBy", "updatedBy")


def _replay_normalize(value):
    if isinstance(value, str):
        if _TIMESTAMP.fullmatch(value):
            return "<timestamp>"
        return _UUID.sub("<uuid>", value)
    if isinstance(value, dict):
        return {
            key: "<actor>" if key in _ACTORS else _replay_normalize(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_replay_normalize(item) for item in value]
    return value


def _replay_body(response, expected) -> None:
    actual = response.json()
    assert _replay_normalize(actual) == _replay_normalize(expected), (
        f"response body differs\nactual:   {actual}\nexpected: {expected}"
    )


async def test_backend_replay_creazione_personaggio_da_browser(
    async_client, app, db_manager
) -> None:
    user = await _replay_user(db_manager)

    async def _session():
        request_session = db_manager.async_session_maker()
        try:
            async with request_session.begin():
                yield request_session
        finally:
            await request_session.close()

    app.dependency_overrides[get_db_session] = _session
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_optional_user] = lambda: user
    # F17: the authenticated landing is /worlds, so the recorded GET / is now a
    # 303 redirect there instead of the retired Home page.
    response = await async_client.request("GET", "/")
    assert response.status_code == 303, f"GET / -> {response.status_code}"
    assert response.headers["location"] == "/worlds"
    response = await async_client.request("GET", "/worlds")
    assert response.status_code == 200, f"GET /worlds -> {response.status_code}"
    response = await async_client.request("GET", "/")
    assert response.status_code == 303, f"GET / -> {response.status_code}"
    response = await async_client.request("GET", "/worlds")
    assert response.status_code == 200, f"GET /worlds -> {response.status_code}"
    response = await async_client.request("GET", "/worlds/new")
    assert response.status_code == 200, f"GET /worlds/new -> {response.status_code}"
    response = await async_client.request(
        "POST", "/worlds/new", json={"name": "Prova", "description": "Prova"}
    )
    assert response.status_code == 204, f"POST /worlds/new -> {response.status_code}"
    world_1 = _replay_id(response)
    response = await async_client.request("GET", f"/worlds/{world_1}")
    assert response.status_code == 200, (
        f"GET /worlds/{world_1} -> {response.status_code}"
    )
    response = await async_client.request("GET", f"/worlds/{world_1}/characters")
    assert response.status_code == 200, (
        f"GET /worlds/{world_1}/characters -> {response.status_code}"
    )
    response = await async_client.request(
        "POST", f"/worlds/{world_1}/characters/new", json={}
    )
    assert response.status_code == 204, (
        f"POST /worlds/{world_1}/characters/new -> {response.status_code}"
    )
    character_1 = _replay_id(response)
    response = await async_client.request(
        "GET", f"/worlds/{world_1}/characters/{character_1}?edit=1"
    )
    assert response.status_code == 200, (
        f"GET /worlds/{world_1}/characters/{character_1}?edit=1 -> {response.status_code}"
    )
    response = await async_client.request(
        "PATCH",
        f"/api/worlds/{world_1}/characters/{character_1}",
        json={"name": "Pippo", "expected_version": 1},
    )
    assert response.status_code == 200, (
        f"PATCH /api/worlds/{world_1}/characters/{character_1} -> {response.status_code}"
    )
    _replay_body(
        response,
        {
            "version": 2,
            "createdAt": "2026-09-21T18:33:06+0000",
            "updatedAt": "2026-09-21T18:33:09+0000",
            "id": "01a0c53e-4098-7c81-8a02-1f1d67470c70",
            "name": "Pippo",
            "title": None,
            "shortDescription": "",
            "tint": "p1",
            "animal": "🐈",
            "imageUrl": None,
            "owner": {
                "createdAt": "2026-09-21T18:30:19+0000",
                "updatedAt": "2026-09-21T18:30:19+0000",
                "id": "01a0c53b-b52c-7490-b3ee-0567d6ce3007",
                "name": "user-1@example.test",
                "email": "user-1@example.test",
                "avatarUrl": None,
                "symbolStyle": "icons",
                "role": "admin",
                "isActive": True,
            },
            "locked": False,
            "isDraft": True,
            "body": "",
        },
    )
    response = await async_client.request(
        "PATCH",
        f"/api/worlds/{world_1}/characters/{character_1}",
        json={"title": "Pipolo", "expected_version": 2},
    )
    assert response.status_code == 200, (
        f"PATCH /api/worlds/{world_1}/characters/{character_1} -> {response.status_code}"
    )
    _replay_body(
        response,
        {
            "version": 3,
            "createdAt": "2026-09-21T18:33:06+0000",
            "updatedAt": "2026-09-21T18:33:13+0000",
            "id": "01a0c53e-4098-7c81-8a02-1f1d67470c70",
            "name": "Pippo",
            "title": "Pipolo",
            "shortDescription": "",
            "tint": "p1",
            "animal": "🐈",
            "imageUrl": None,
            "owner": {
                "createdAt": "2026-09-21T18:30:19+0000",
                "updatedAt": "2026-09-21T18:30:19+0000",
                "id": "01a0c53b-b52c-7490-b3ee-0567d6ce3007",
                "name": "user-1@example.test",
                "email": "user-1@example.test",
                "avatarUrl": None,
                "symbolStyle": "icons",
                "role": "admin",
                "isActive": True,
            },
            "locked": False,
            "isDraft": True,
            "body": "",
        },
    )
    response = await async_client.request(
        "PATCH",
        f"/api/worlds/{world_1}/characters/{character_1}",
        json={"short_description": "Azzarella", "expected_version": 3},
    )
    assert response.status_code == 200, (
        f"PATCH /api/worlds/{world_1}/characters/{character_1} -> {response.status_code}"
    )
    _replay_body(
        response,
        {
            "version": 4,
            "createdAt": "2026-09-21T18:33:06+0000",
            "updatedAt": "2026-09-21T18:33:24+0000",
            "id": "01a0c53e-4098-7c81-8a02-1f1d67470c70",
            "name": "Pippo",
            "title": "Pipolo",
            "shortDescription": "Azzarella",
            "tint": "p1",
            "animal": "🐈",
            "imageUrl": None,
            "owner": {
                "createdAt": "2026-09-21T18:30:19+0000",
                "updatedAt": "2026-09-21T18:30:19+0000",
                "id": "01a0c53b-b52c-7490-b3ee-0567d6ce3007",
                "name": "user-1@example.test",
                "email": "user-1@example.test",
                "avatarUrl": None,
                "symbolStyle": "icons",
                "role": "admin",
                "isActive": True,
            },
            "locked": False,
            "isDraft": True,
            "body": "",
        },
    )
    response = await async_client.request(
        "PATCH",
        f"/api/worlds/{world_1}/characters/{character_1}",
        json={"tint": "p2", "expected_version": 4},
    )
    assert response.status_code == 200, (
        f"PATCH /api/worlds/{world_1}/characters/{character_1} -> {response.status_code}"
    )
    _replay_body(
        response,
        {
            "version": 5,
            "createdAt": "2026-09-21T18:33:06+0000",
            "updatedAt": "2026-09-21T18:33:24+0000",
            "id": "01a0c53e-4098-7c81-8a02-1f1d67470c70",
            "name": "Pippo",
            "title": "Pipolo",
            "shortDescription": "Azzarella",
            "tint": "p2",
            "animal": "🐈",
            "imageUrl": None,
            "owner": {
                "createdAt": "2026-09-21T18:30:19+0000",
                "updatedAt": "2026-09-21T18:30:19+0000",
                "id": "01a0c53b-b52c-7490-b3ee-0567d6ce3007",
                "name": "user-1@example.test",
                "email": "user-1@example.test",
                "avatarUrl": None,
                "symbolStyle": "icons",
                "role": "admin",
                "isActive": True,
            },
            "locked": False,
            "isDraft": True,
            "body": "",
        },
    )
    response = await async_client.request(
        "GET", f"/worlds/{world_1}/characters/{character_1}?edit=1"
    )
    assert response.status_code == 200, (
        f"GET /worlds/{world_1}/characters/{character_1}?edit=1 -> {response.status_code}"
    )
    response = await async_client.request(
        "PATCH",
        f"/api/worlds/{world_1}/characters/{character_1}",
        json={"animal": "🐸", "expected_version": 5},
    )
    assert response.status_code == 200, (
        f"PATCH /api/worlds/{world_1}/characters/{character_1} -> {response.status_code}"
    )
    _replay_body(
        response,
        {
            "version": 6,
            "createdAt": "2026-09-21T18:33:06+0000",
            "updatedAt": "2026-09-21T18:33:25+0000",
            "id": "01a0c53e-4098-7c81-8a02-1f1d67470c70",
            "name": "Pippo",
            "title": "Pipolo",
            "shortDescription": "Azzarella",
            "tint": "p2",
            "animal": "🐸",
            "imageUrl": None,
            "owner": {
                "createdAt": "2026-09-21T18:30:19+0000",
                "updatedAt": "2026-09-21T18:30:19+0000",
                "id": "01a0c53b-b52c-7490-b3ee-0567d6ce3007",
                "name": "user-1@example.test",
                "email": "user-1@example.test",
                "avatarUrl": None,
                "symbolStyle": "icons",
                "role": "admin",
                "isActive": True,
            },
            "locked": False,
            "isDraft": True,
            "body": "",
        },
    )
    response = await async_client.request(
        "GET", f"/worlds/{world_1}/characters/{character_1}?edit=1"
    )
    assert response.status_code == 200, (
        f"GET /worlds/{world_1}/characters/{character_1}?edit=1 -> {response.status_code}"
    )
    response = await async_client.request(
        "PATCH",
        f"/api/worlds/{world_1}/characters/{character_1}",
        json={"animal": "🐍", "expected_version": 6},
    )
    assert response.status_code == 200, (
        f"PATCH /api/worlds/{world_1}/characters/{character_1} -> {response.status_code}"
    )
    _replay_body(
        response,
        {
            "version": 7,
            "createdAt": "2026-09-21T18:33:06+0000",
            "updatedAt": "2026-09-21T18:33:27+0000",
            "id": "01a0c53e-4098-7c81-8a02-1f1d67470c70",
            "name": "Pippo",
            "title": "Pipolo",
            "shortDescription": "Azzarella",
            "tint": "p2",
            "animal": "🐍",
            "imageUrl": None,
            "owner": {
                "createdAt": "2026-09-21T18:30:19+0000",
                "updatedAt": "2026-09-21T18:30:19+0000",
                "id": "01a0c53b-b52c-7490-b3ee-0567d6ce3007",
                "name": "user-1@example.test",
                "email": "user-1@example.test",
                "avatarUrl": None,
                "symbolStyle": "icons",
                "role": "admin",
                "isActive": True,
            },
            "locked": False,
            "isDraft": True,
            "body": "",
        },
    )
    response = await async_client.request(
        "GET", f"/worlds/{world_1}/characters/{character_1}?edit=1"
    )
    assert response.status_code == 200, (
        f"GET /worlds/{world_1}/characters/{character_1}?edit=1 -> {response.status_code}"
    )
    response = await async_client.request(
        "PATCH",
        f"/api/worlds/{world_1}/characters/{character_1}",
        json={"tint": "p8", "expected_version": 7},
    )
    assert response.status_code == 200, (
        f"PATCH /api/worlds/{world_1}/characters/{character_1} -> {response.status_code}"
    )
    _replay_body(
        response,
        {
            "version": 8,
            "createdAt": "2026-09-21T18:33:06+0000",
            "updatedAt": "2026-09-21T18:33:28+0000",
            "id": "01a0c53e-4098-7c81-8a02-1f1d67470c70",
            "name": "Pippo",
            "title": "Pipolo",
            "shortDescription": "Azzarella",
            "tint": "p8",
            "animal": "🐍",
            "imageUrl": None,
            "owner": {
                "createdAt": "2026-09-21T18:30:19+0000",
                "updatedAt": "2026-09-21T18:30:19+0000",
                "id": "01a0c53b-b52c-7490-b3ee-0567d6ce3007",
                "name": "user-1@example.test",
                "email": "user-1@example.test",
                "avatarUrl": None,
                "symbolStyle": "icons",
                "role": "admin",
                "isActive": True,
            },
            "locked": False,
            "isDraft": True,
            "body": "",
        },
    )
    response = await async_client.request(
        "GET", f"/worlds/{world_1}/characters/{character_1}?edit=1"
    )
    assert response.status_code == 200, (
        f"GET /worlds/{world_1}/characters/{character_1}?edit=1 -> {response.status_code}"
    )
    response = await async_client.request(
        "POST",
        f"/worlds/{world_1}/characters/{character_1}/toggle/is_draft?value=false",
        json={},
    )
    assert response.status_code == 204, (
        f"POST /worlds/{world_1}/characters/{character_1}/toggle/is_draft?value=false -> {response.status_code}"
    )
    response = await async_client.request(
        "GET", f"/worlds/{world_1}/characters/{character_1}"
    )
    assert response.status_code == 200, (
        f"GET /worlds/{world_1}/characters/{character_1} -> {response.status_code}"
    )
    response = await async_client.request("GET", f"/worlds/{world_1}/characters")
    assert response.status_code == 200, (
        f"GET /worlds/{world_1}/characters -> {response.status_code}"
    )
    response = await async_client.request(
        "GET", f"/worlds/{world_1}/characters/{character_1}"
    )
    assert response.status_code == 200, (
        f"GET /worlds/{world_1}/characters/{character_1} -> {response.status_code}"
    )
    response = await async_client.request(
        "PATCH",
        f"/api/worlds/{world_1}/characters/{character_1}",
        json={"animal": "🐁", "expected_version": 9},
    )
    assert response.status_code == 200, (
        f"PATCH /api/worlds/{world_1}/characters/{character_1} -> {response.status_code}"
    )
    _replay_body(
        response,
        {
            "version": 10,
            "createdAt": "2026-09-21T18:33:06+0000",
            "updatedAt": "2026-09-21T18:33:35+0000",
            "id": "01a0c53e-4098-7c81-8a02-1f1d67470c70",
            "name": "Pippo",
            "title": "Pipolo",
            "shortDescription": "Azzarella",
            "tint": "p8",
            "animal": "🐁",
            "imageUrl": None,
            "owner": {
                "createdAt": "2026-09-21T18:30:19+0000",
                "updatedAt": "2026-09-21T18:30:19+0000",
                "id": "01a0c53b-b52c-7490-b3ee-0567d6ce3007",
                "name": "user-1@example.test",
                "email": "user-1@example.test",
                "avatarUrl": None,
                "symbolStyle": "icons",
                "role": "admin",
                "isActive": True,
            },
            "locked": False,
            "isDraft": False,
            "body": "",
        },
    )
    response = await async_client.request(
        "GET", f"/worlds/{world_1}/characters/{character_1}"
    )
    assert response.status_code == 200, (
        f"GET /worlds/{world_1}/characters/{character_1} -> {response.status_code}"
    )
    response = await async_client.request(
        "PATCH",
        f"/api/worlds/{world_1}/characters/{character_1}",
        json={"animal": "🐍", "expected_version": 10},
    )
    assert response.status_code == 200, (
        f"PATCH /api/worlds/{world_1}/characters/{character_1} -> {response.status_code}"
    )
    _replay_body(
        response,
        {
            "version": 11,
            "createdAt": "2026-09-21T18:33:06+0000",
            "updatedAt": "2026-09-21T18:33:36+0000",
            "id": "01a0c53e-4098-7c81-8a02-1f1d67470c70",
            "name": "Pippo",
            "title": "Pipolo",
            "shortDescription": "Azzarella",
            "tint": "p8",
            "animal": "🐍",
            "imageUrl": None,
            "owner": {
                "createdAt": "2026-09-21T18:30:19+0000",
                "updatedAt": "2026-09-21T18:30:19+0000",
                "id": "01a0c53b-b52c-7490-b3ee-0567d6ce3007",
                "name": "user-1@example.test",
                "email": "user-1@example.test",
                "avatarUrl": None,
                "symbolStyle": "icons",
                "role": "admin",
                "isActive": True,
            },
            "locked": False,
            "isDraft": False,
            "body": "",
        },
    )
    response = await async_client.request(
        "GET", f"/worlds/{world_1}/characters/{character_1}"
    )
    assert response.status_code == 200, (
        f"GET /worlds/{world_1}/characters/{character_1} -> {response.status_code}"
    )
    response = await async_client.request(
        "POST",
        f"/worlds/{world_1}/characters/{character_1}/toggle/locked?value=true",
        json={},
    )
    assert response.status_code == 204, (
        f"POST /worlds/{world_1}/characters/{character_1}/toggle/locked?value=true -> {response.status_code}"
    )
    response = await async_client.request(
        "GET", f"/worlds/{world_1}/characters/{character_1}"
    )
    assert response.status_code == 200, (
        f"GET /worlds/{world_1}/characters/{character_1} -> {response.status_code}"
    )
    response = await async_client.request("GET", f"/worlds/{world_1}")
    assert response.status_code == 200, (
        f"GET /worlds/{world_1} -> {response.status_code}"
    )
    response = await async_client.request("GET", f"/worlds/{world_1}")
    assert response.status_code == 200, (
        f"GET /worlds/{world_1} -> {response.status_code}"
    )
    response = await async_client.request("GET", f"/worlds/{world_1}/characters")
    assert response.status_code == 200, (
        f"GET /worlds/{world_1}/characters -> {response.status_code}"
    )
    response = await async_client.request(
        "GET", f"/worlds/{world_1}/characters/{character_1}"
    )
    assert response.status_code == 200, (
        f"GET /worlds/{world_1}/characters/{character_1} -> {response.status_code}"
    )
    response = await async_client.request("GET", f"/worlds/{world_1}")
    assert response.status_code == 200, (
        f"GET /worlds/{world_1} -> {response.status_code}"
    )
