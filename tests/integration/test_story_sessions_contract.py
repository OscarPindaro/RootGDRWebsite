"""The persisted story-session contract (REQ-0010/T02).

A story exposes the sessions it is composed of as a read-only, additive
reference list, so a client can update counts and names from an authenticated
response. References are validated like the sessions list: duplicates, another
world and an unseen draft are refused with a typed 422, never a 500, and a
reader never learns a draft's title through a story.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from src.backend.auth.dependencies import get_current_user
from src.backend.config import AppConfig
from src.backend.db.db import DatabaseManager
from src.backend.db.enums import UserRole, WorldRole
from src.backend.server import create_app
from src.backend.users.models import UserModel
from src.backend.users.schemas import User
from src.backend.worlds.models import WorldModel

pytestmark = pytest.mark.integration


class _Stories:
    def __init__(
        self,
        client: AsyncClient,
        app: FastAPI,
        world_id: uuid.UUID,
        other_world_id: uuid.UUID,
        master: User,
        reader: User,
    ):
        self.client = client
        self.app = app
        self.world_id = world_id
        self.other_world_id = other_world_id
        self.master = master
        self.reader = reader

    def act_as(self, user: User) -> None:
        self.app.dependency_overrides[get_current_user] = lambda: user

    def url(self, path: str = "") -> str:
        return f"/api/worlds/{self.world_id}/stories{path}"

    async def session(self, title: str, **extra) -> dict:
        payload = {"title": title, "in_world_date": "Autunno", **extra}
        response = await self.client.post(
            f"/api/worlds/{self.world_id}/sessions/", json=payload
        )
        assert response.status_code == 201, response.text
        return response.json()


@pytest_asyncio.fixture
async def stories(
    app_config: AppConfig, db_manager: DatabaseManager
) -> AsyncGenerator[_Stories, None]:
    app: FastAPI = create_app(app_config)
    app.state.db_manager = db_manager
    created: dict[str, uuid.UUID] = {}
    session = db_manager.async_session_maker()
    async with session.begin():
        master_model = UserModel(
            name="story-master",
            email=f"story-master-{uuid.uuid4()}@example.com",
            role=UserRole.MEMBER,
        )
        reader_model = UserModel(
            name="story-reader",
            email=f"story-reader-{uuid.uuid4()}@example.com",
            role=UserRole.MEMBER,
        )
        session.add(master_model)
        session.add(reader_model)
        await session.flush()
        created["master"] = master_model.id
        created["reader"] = reader_model.id
        master = User.model_validate(master_model)
    await session.close()

    app.dependency_overrides[get_current_user] = lambda: master

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        first = await client.post(
            "/api/worlds/",
            json={
                "name": "Boscochiaro",
                "description": "x",
                "members": [{"user_id": str(reader_model.id), "role": "master"}],
            },
        )
        second = await client.post(
            "/api/worlds/", json={"name": "Altrove", "description": "y"}
        )
        world_id = uuid.UUID(first.json()["id"])
        other_world_id = uuid.UUID(second.json()["id"])
        created["world"] = world_id
        created["other"] = other_world_id
        yield _Stories(
            client,
            app,
            world_id,
            other_world_id,
            master,
            User.model_validate(reader_model),
        )

    session = db_manager.async_session_maker()
    async with session.begin():
        for key in ("world", "other"):
            await session.execute(
                delete(WorldModel).where(WorldModel.id == created[key])
            )
        for key in ("master", "reader"):
            await session.execute(delete(UserModel).where(UserModel.id == created[key]))
    await session.close()


async def test_a_story_reports_its_sessions(stories: _Stories) -> None:
    first = await stories.session("Il risveglio")
    second = await stories.session("L'inverno dei corvi", tint="p8")

    created = await stories.client.post(
        stories.url("/"),
        json={"title": "Arco", "session_ids": [first["id"], second["id"]]},
    )
    assert created.status_code == 201, created.text
    references = created.json()["sessions"]
    assert [row["title"] for row in references] == [
        "Il risveglio",
        "L'inverno dei corvi",
    ]
    assert references[1]["tint"] == "p8"

    fetched = await stories.client.get(stories.url(f"/{created.json()['id']}"))
    assert len(fetched.json()["sessions"]) == 2


async def test_removing_and_emptying_the_relationship(stories: _Stories) -> None:
    only = await stories.session("Unica")
    story = (
        await stories.client.post(
            stories.url("/"), json={"title": "Arco", "session_ids": [only["id"]]}
        )
    ).json()

    cleared = await stories.client.patch(
        stories.url(f"/{story['id']}"),
        json={"session_ids": [], "expected_version": story["version"]},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["sessions"] == []


async def test_a_duplicated_reference_is_refused(stories: _Stories) -> None:
    only = await stories.session("Unica")

    refused = await stories.client.post(
        stories.url("/"),
        json={"title": "Arco", "session_ids": [only["id"], only["id"]]},
    )

    assert refused.status_code == 422
    assert "duplicat" in refused.json()["detail"].lower()


async def test_another_world_session_is_refused(stories: _Stories) -> None:
    other = (
        await stories.client.post(
            f"/api/worlds/{stories.other_world_id}/sessions/",
            json={"title": "Altrove", "in_world_date": "Estate"},
        )
    ).json()

    refused = await stories.client.post(
        stories.url("/"), json={"title": "Arco", "session_ids": [other["id"]]}
    )

    assert refused.status_code == 422
    assert "visibili" in refused.json()["detail"]


async def test_an_unseen_draft_is_refused_and_never_leaks(
    stories: _Stories,
) -> None:
    draft = await stories.session("Bozza del master", is_draft=True)
    story = (
        await stories.client.post(
            stories.url("/"), json={"title": "Arco", "session_ids": [draft["id"]]}
        )
    ).json()

    stories.act_as(stories.reader)
    # A reader cannot reference it and cannot read it through the story.
    refused = await stories.client.post(
        stories.url("/"), json={"title": "Arco altrui", "session_ids": [draft["id"]]}
    )
    assert refused.status_code == 422
    fetched = await stories.client.get(stories.url(f"/{story['id']}"))
    assert fetched.status_code == 200
    assert fetched.json()["sessions"] == []

    stories.act_as(stories.master)
    fetched = await stories.client.get(stories.url(f"/{story['id']}"))
    assert [row["title"] for row in fetched.json()["sessions"]] == ["Bozza del master"]
