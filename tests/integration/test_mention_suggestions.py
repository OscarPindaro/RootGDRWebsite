"""Mention suggestions: bounded, filtered like the lists, with mark cues.

The ``@`` menu must offer the same visibility a reader has in the lists (a
draft belongs to its author), never ship a whole world to produce eight
suggestions, and carry the stored mark tokens (``animal``, ``shape``) so the
client can draw a fixed mark — never HTML built from a user's name.
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
from src.backend.db.enums import UserRole
from src.backend.server import create_app
from src.backend.users.models import UserModel
from src.backend.users.schemas import User
from src.backend.worlds.models import WorldModel

pytestmark = pytest.mark.integration


class _Suggestions:
    def __init__(self, client: AsyncClient, world_id: uuid.UUID, author: User):
        self.client = client
        self.world_id = world_id
        self.author = author

    async def get(self, q: str = "") -> list[dict]:
        response = await self.client.get(
            f"/api/worlds/{self.world_id}/mentions", params={"q": q}
        )
        assert response.status_code == 200, response.text
        return response.json()["data"]

    def url(self, collection: str) -> str:
        return f"/api/worlds/{self.world_id}/{collection}/"


@pytest_asyncio.fixture
async def suggestions(
    app_config: AppConfig, db_manager: DatabaseManager
) -> AsyncGenerator[_Suggestions, None]:
    app: FastAPI = create_app(app_config)
    app.state.db_manager = db_manager
    created: dict[str, uuid.UUID] = {}
    session = db_manager.async_session_maker()
    async with session.begin():
        author_model = UserModel(
            name="author",
            email=f"mentions-author-{uuid.uuid4()}@example.com",
            role=UserRole.MEMBER,
        )
        reader_model = UserModel(
            name="reader",
            email=f"mentions-reader-{uuid.uuid4()}@example.com",
            role=UserRole.MEMBER,
        )
        session.add(author_model)
        session.add(reader_model)
        await session.flush()
        created["author"] = author_model.id
        created["reader"] = reader_model.id
        author = User.model_validate(author_model)
    await session.close()

    app.dependency_overrides[get_current_user] = lambda: author

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        first = await client.post(
            "/api/worlds/",
            json={
                "name": "Boscochiaro",
                "description": "x",
                "members": [{"user_id": str(reader_model.id), "role": "player"}],
            },
        )
        second = await client.post(
            "/api/worlds/", json={"name": "Altrove", "description": "y"}
        )
        world_id = uuid.UUID(first.json()["id"])
        other_world_id = uuid.UUID(second.json()["id"])
        created["world"] = world_id
        created["other"] = other_world_id
        api = _Suggestions(client, world_id, author)

        # The author's published character and place, plus their own draft.
        character = await client.post(
            api.url("characters"),
            json={"name": "Fiamma Rossa", "animal": "🐈", "is_draft": False},
        )
        assert character.status_code == 201, character.text
        place = await client.post(
            api.url("places"),
            json={"name": "Radura", "shape": "rombo", "is_draft": False},
        )
        assert place.status_code == 201, place.text
        draft = await client.post(
            api.url("characters"), json={"name": "Bozza Mia", "is_draft": True}
        )
        assert draft.status_code == 201, draft.text
        await client.post(
            f"/api/worlds/{other_world_id}/characters/",
            json={"name": "Altrove Personaggio"},
        )

        # Another author's draft: only its author may see it.
        app.dependency_overrides[get_current_user] = lambda: reader_model
        other_draft = await client.post(
            api.url("characters"),
            json={"name": "Bozza Altrui", "is_draft": True},
        )
        assert other_draft.status_code == 201, other_draft.text
        other_published = await client.post(
            api.url("characters"),
            json={"name": "Pubblicata Altrui", "is_draft": False},
        )
        assert other_published.status_code == 201, other_published.text
        app.dependency_overrides[get_current_user] = lambda: author

        # More than the cap, to prove the suggestion list is bounded.
        for index in range(10):
            await client.post(
                api.url("characters"), json={"name": f"Bosco {index:02d}"}
            )

        yield api

    session = db_manager.async_session_maker()
    async with session.begin():
        for key in ("world", "other"):
            await session.execute(
                delete(WorldModel).where(WorldModel.id == created[key])
            )
        for key in ("author", "reader"):
            await session.execute(delete(UserModel).where(UserModel.id == created[key]))
    await session.close()


async def test_suggestions_carry_the_mark_cues(suggestions: _Suggestions) -> None:
    rows = {row["name"]: row for row in await suggestions.get("Fiamma")}
    assert rows["Fiamma Rossa"]["animal"] == "🐈"
    assert rows["Fiamma Rossa"]["shape"] is None
    assert rows["Fiamma Rossa"]["kind"] == "personaggio"

    places = {row["name"]: row for row in await suggestions.get("Radura")}
    assert places["Radura"]["shape"] == "rombo"
    assert places["Radura"]["animal"] is None


async def test_a_draft_is_only_suggested_to_its_author(
    suggestions: _Suggestions,
) -> None:
    names = {row["name"] for row in await suggestions.get("Bozza")}

    assert "Bozza Mia" in names
    assert "Bozza Altrui" not in names
    # Published documents by anyone are visible.
    published = {row["name"] for row in await suggestions.get("Pubblicata")}
    assert "Pubblicata Altrui" in published


async def test_another_world_never_leaks_in(suggestions: _Suggestions) -> None:
    assert await suggestions.get("Altrove") == []


async def test_the_suggestion_list_is_bounded(suggestions: _Suggestions) -> None:
    rows = await suggestions.get("Bosco")

    assert len(rows) <= 8


async def test_an_ambiguous_name_is_qualified_and_stays_plain_text(
    suggestions: _Suggestions,
) -> None:
    await suggestions.client.post(
        suggestions.url("places"), json={"name": "Fiamma Rossa"}
    )

    rows = await suggestions.get("Fiamma")
    labels = {row["insert"] for row in rows}
    assert labels == {"personaggio:Fiamma Rossa", "luogo:Fiamma Rossa"}


async def test_a_hostile_name_is_returned_as_data(suggestions: _Suggestions) -> None:
    hostile = "<script>alert(1)</script>"
    await suggestions.client.post(suggestions.url("characters"), json={"name": hostile})

    rows = await suggestions.get("<script>")

    assert [row["name"] for row in rows] == [hostile]
    assert all("<svg" not in row["name"] for row in rows)
