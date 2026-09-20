"""End-to-end HTTP checks over the JSON API.

Exercises route + service + database together (no mocks) for the character
slice: create, read, update, delete, validation, authorization and cross-world
isolation. The session commits so a later request can see an earlier one.
"""

import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.auth.dependencies import get_current_user
from src.backend.config import AppConfig
from src.backend.db.db import DatabaseManager
from src.backend.db.enums import UserRole
from src.backend.dependencies import get_db_session
from src.backend.server import create_app
from src.backend.users.models import UserModel
from src.backend.users.schemas import User
from src.backend.worlds.models import WorldModel

pytestmark = pytest.mark.integration


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

    async def _session() -> AsyncGenerator[AsyncSession, None]:
        session = db_manager.async_session_maker()
        try:
            async with session.begin():
                yield session
        finally:
            await session.close()

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

    app.dependency_overrides[get_db_session] = _session
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


async def test_unknown_world_is_not_found(api: _Api) -> None:
    response = await api.client.get(f"/api/worlds/{uuid.uuid4()}/characters/")
    assert response.status_code == 404
