"""End-to-end HTTP checks over the JSON API.

Exercises route + service + database together (no mocks) for the character
slice: create, read, update, delete, validation, authorization and cross-world
isolation. The session commits so a later request can see an earlier one.
"""

import asyncio
import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from src.backend.auth.dependencies import get_current_user
from src.backend.config import AppConfig
from src.backend.db.db import DatabaseManager
from src.backend.db.enums import UserRole
from src.backend.server import create_app
from src.backend.users.models import UserModel
from src.backend.users.schemas import User
from src.backend.worlds.models import WorldModel

pytestmark = pytest.mark.integration

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 8
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 12


class _Api:
    def __init__(
        self, client: AsyncClient, world_id: uuid.UUID, other_world_id: uuid.UUID
    ):
        self.client = client
        self.world_id = world_id
        self.other_world_id = other_world_id

    def url(self, path: str = "") -> str:
        return f"/api/worlds/{self.world_id}/characters{path}"


@pytest_asyncio.fixture
async def api(
    app_config: AppConfig, db_manager: DatabaseManager
) -> AsyncGenerator[_Api, None]:
    app: FastAPI = create_app(app_config)

    app.state.db_manager = db_manager
    created: dict[str, uuid.UUID] = {}
    session = db_manager.async_session_maker()
    async with session.begin():
        owner = UserModel(
            name="api-owner",
            email=f"api-owner-{uuid.uuid4()}@example.com",
            role=UserRole.MEMBER,
        )
        session.add(owner)
        await session.flush()
        created["user"] = owner.id
        user = User.model_validate(owner)
    await session.close()

    app.dependency_overrides[get_current_user] = lambda: user

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        first = await client.post(
            "/api/worlds/", json={"name": "Boscochiaro", "description": "x"}
        )
        second = await client.post(
            "/api/worlds/", json={"name": "Altrove", "description": "y"}
        )
        world_id = uuid.UUID(first.json()["id"])
        other_world_id = uuid.UUID(second.json()["id"])
        created["world"] = world_id
        created["other"] = other_world_id
        yield _Api(client, world_id, other_world_id)

    session = db_manager.async_session_maker()
    async with session.begin():
        await session.execute(
            delete(WorldModel).where(WorldModel.created_by_id == created["user"])
        )
        await session.execute(delete(UserModel).where(UserModel.id == created["user"]))
    await session.close()


async def test_world_image_revision_api(api: _Api) -> None:
    image_url = f"/api/worlds/{api.world_id}/image"
    first_upload = await api.client.put(
        image_url, files={"image": ("a.png", PNG, "image/png")}
    )
    assert first_upload.status_code == 200
    assert first_upload.json()["version"] == 2
    second_upload = await api.client.put(
        image_url, files={"image": ("b.jpg", JPEG, "image/jpeg")}
    )
    assert second_upload.status_code == 200
    assert second_upload.json()["version"] == 3

    history_url = f"/api/worlds/{api.world_id}/images/world/{api.world_id}/revisions"
    listed = await api.client.get(f"{history_url}/")
    assert listed.status_code == 200
    newest, oldest = listed.json()["data"]
    assert [newest["filename"], oldest["filename"]] == ["b.jpg", "a.png"]
    assert newest["uploaded_by_name"] == "api-owner"
    assert newest["is_current"] is True

    content = await api.client.get(f"{history_url}/{oldest['id']}/content")
    assert content.status_code == 200
    assert content.content == PNG
    assert content.headers["x-content-type-options"] == "nosniff"

    restored = await api.client.post(f"{history_url}/{oldest['id']}/restore")
    assert restored.status_code == 200
    assert restored.json()["is_current"] is True
    assert (await api.client.get(f"/api/worlds/{api.world_id}")).json()["version"] == 4
    deleted = await api.client.delete(f"{history_url}/{newest['id']}")
    assert deleted.status_code == 204
    assert (await api.client.delete(f"{history_url}/current")).status_code == 204
    assert (await api.client.get(f"/api/worlds/{api.world_id}")).json()["version"] == 5

    cross_world = await api.client.get(
        f"/api/worlds/{api.other_world_id}/images/world/{api.world_id}/revisions/"
    )
    assert cross_world.status_code == 404


async def test_world_version_and_stale_update(api: _Api) -> None:
    fetched = await api.client.get(f"/api/worlds/{api.world_id}")
    assert fetched.json()["version"] == 1

    updated = await api.client.patch(
        f"/api/worlds/{api.world_id}",
        json={"description": "updated", "expected_version": 1},
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2

    stale = await api.client.patch(
        f"/api/worlds/{api.world_id}",
        json={"description": "stale", "expected_version": 1},
    )
    assert stale.status_code == 409


async def test_character_crud_over_http(api: _Api) -> None:
    created = await api.client.post(
        api.url("/"),
        json={"name": "Rugginosa", "tint": "p1", "animal": "🐈", "body": "Ciao"},
    )
    assert created.status_code == 201
    character = created.json()
    assert character["name"] == "Rugginosa"

    fetched = await api.client.get(api.url(f"/{character['id']}"))
    assert fetched.status_code == 200
    assert fetched.json()["body"] == "Ciao"

    updated = await api.client.patch(
        api.url(f"/{character['id']}"), json={"title": "La Senza Tana"}
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "La Senza Tana"

    listed = await api.client.get(api.url("/"))
    assert [c["name"] for c in listed.json()["data"]] == ["Rugginosa"]

    deleted = await api.client.delete(api.url(f"/{character['id']}"))
    assert deleted.status_code == 204
    missing = await api.client.get(api.url(f"/{character['id']}"))
    assert missing.status_code == 404


async def test_version_increment_stale_update_lock_and_unlock(api: _Api) -> None:
    created = await api.client.post(api.url("/"), json={"name": "Versionata"})
    character = created.json()
    assert character["version"] == 1

    updated = await api.client.patch(
        api.url(f"/{character['id']}"),
        json={"title": "Prima", "expected_version": character["version"]},
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2

    stale = await api.client.patch(
        api.url(f"/{character['id']}"),
        json={"title": "Persa", "expected_version": 1},
    )
    assert stale.status_code == 409
    fetched = await api.client.get(api.url(f"/{character['id']}"))
    assert fetched.json()["title"] == "Prima"

    locked = await api.client.patch(
        api.url(f"/{character['id']}"),
        json={"locked": True, "expected_version": 2},
    )
    assert locked.status_code == 200
    assert locked.json()["version"] == 3

    rejected = await api.client.patch(
        api.url(f"/{character['id']}"),
        json={"body": "no", "expected_version": 3},
    )
    assert rejected.status_code == 423

    mixed_unlock = await api.client.patch(
        api.url(f"/{character['id']}"),
        json={"locked": False, "body": "no", "expected_version": 3},
    )
    assert mixed_unlock.status_code == 423

    unlocked = await api.client.patch(
        api.url(f"/{character['id']}"),
        json={"locked": False, "expected_version": 3},
    )
    assert unlocked.status_code == 200
    assert unlocked.json()["locked"] is False
    assert unlocked.json()["version"] == 4


async def test_content_toggles_use_current_version_and_respect_lock(api: _Api) -> None:
    created = await api.client.post(api.url("/"), json={"name": "Toggle"})
    character = created.json()
    base = f"/worlds/{api.world_id}/characters/{character['id']}/toggle"

    locked = await api.client.post(f"{base}/locked?value=true")
    assert locked.status_code == 204
    after_lock = await api.client.get(api.url(f"/{character['id']}"))
    assert after_lock.json()["version"] == 2

    publish = await api.client.post(f"{base}/is_draft?value=true")
    assert publish.status_code == 423

    unlocked = await api.client.post(f"{base}/locked?value=false")
    assert unlocked.status_code == 204
    after_unlock = await api.client.get(api.url(f"/{character['id']}"))
    assert after_unlock.json()["locked"] is False
    assert after_unlock.json()["version"] == 3


async def test_concurrent_updates_return_one_conflict(api: _Api) -> None:
    created = await api.client.post(api.url("/"), json={"name": "Contesa"})
    character = created.json()
    url = api.url(f"/{character['id']}")

    first, second = await asyncio.gather(
        api.client.patch(url, json={"title": "A", "expected_version": 1}),
        api.client.patch(url, json={"title": "B", "expected_version": 1}),
    )

    assert sorted((first.status_code, second.status_code)) == [200, 409]
    fetched = await api.client.get(url)
    assert fetched.json()["version"] == 2
    assert fetched.json()["title"] in {"A", "B"}


async def test_mention_suggestions_qualify_ambiguous_names(api: _Api) -> None:
    character = await api.client.post(api.url("/"), json={"name": "Roccianera"})
    place = await api.client.post(
        f"/api/worlds/{api.world_id}/places/", json={"name": "Roccianera"}
    )
    assert character.status_code == 201
    assert place.status_code == 201

    response = await api.client.get(
        f"/api/worlds/{api.world_id}/mentions", params={"q": "Roccia"}
    )
    assert response.status_code == 200
    suggestions = response.json()["data"]
    assert {(item["kind"], item["insert"]) for item in suggestions} == {
        ("personaggio", "personaggio:Roccianera"),
        ("luogo", "luogo:Roccianera"),
    }


async def test_validation_rejects_unknown_animal(api: _Api) -> None:
    response = await api.client.post(
        api.url("/"), json={"name": "X", "animal": "not-an-animal"}
    )
    assert response.status_code == 422


async def test_cross_world_ids_do_not_leak(api: _Api) -> None:
    created = await api.client.post(api.url("/"), json={"name": "Rugginosa"})
    character_id = created.json()["id"]

    # The right id under the wrong world is a 404.
    response = await api.client.get(
        f"/api/worlds/{api.other_world_id}/characters/{character_id}"
    )
    assert response.status_code == 404
    update = await api.client.patch(
        f"/api/worlds/{api.other_world_id}/characters/{character_id}",
        json={"name": "Leaked", "expected_version": 1},
    )
    assert update.status_code == 404


async def test_unknown_world_is_not_found(api: _Api) -> None:
    response = await api.client.get(f"/api/worlds/{uuid.uuid4()}/characters/")
    assert response.status_code == 404
