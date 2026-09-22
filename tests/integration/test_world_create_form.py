"""The world-form create flow.

F13 keeps one create-flow test per distinct route behaviour. The world form
(``POST /worlds/new``, a real htmx form) is the counterpart of the draft-first
content POST tested in ``test_character_list_create_card.py``: it does not land
in name editing, it creates the world and redirects to it.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.auth.dependencies import get_current_user
from src.backend.config import AppConfig
from src.backend.db.db import DatabaseManager
from src.backend.db.enums import UserRole
from src.backend.dependencies import get_db_session
from src.backend.server import create_app
from src.backend.users.models import UserModel
from src.backend.users.schemas import User
from src.backend.worlds.models import WorldMembershipModel, WorldModel

pytestmark = pytest.mark.integration


async def test_the_world_form_creates_a_world(
    app_config: AppConfig, db_manager: DatabaseManager
) -> None:
    email = f"world-form-{uuid.uuid4()}@example.com"
    session = db_manager.async_session_maker()
    async with session.begin():
        model = UserModel(name="Autore", email=email, role=UserRole.MEMBER)
        session.add(model)
        await session.flush()
        user = User.model_validate(model)
    await session.close()

    app: FastAPI = create_app(app_config)

    async def _session() -> AsyncGenerator[AsyncSession, None]:
        request_session = db_manager.async_session_maker()
        try:
            async with request_session.begin():
                yield request_session
        finally:
            await request_session.close()

    app.dependency_overrides[get_db_session] = _session
    app.dependency_overrides[get_current_user] = lambda: user

    world_id: uuid.UUID | None = None
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            form = await client.get("/worlds/new")
            assert form.status_code == 200
            # The form posts to the world route and carries the submit control.
            assert 'hx-post="/worlds/new"' in form.text
            assert 'data-testid="save-world"' in form.text

            created = await client.post(
                "/worlds/new",
                json={"name": "Mondo dal modulo", "description": "d"},
                headers={"HX-Request": "true"},
            )
            assert created.status_code == 204
            location = created.headers["hx-redirect"]
            assert location.startswith("/worlds/"), location
            world_id = uuid.UUID(location.removeprefix("/worlds/"))

            detail = await client.get(location)
            assert detail.status_code == 200
            assert "Mondo dal modulo" in detail.text
    finally:
        if world_id is not None:
            async with db_manager.async_session_maker() as cleanup:
                async with cleanup.begin():
                    await cleanup.execute(
                        delete(WorldMembershipModel).where(
                            WorldMembershipModel.world_id == world_id
                        )
                    )
                    await cleanup.execute(
                        delete(WorldModel).where(WorldModel.id == world_id)
                    )
        async with db_manager.async_session_maker() as cleanup:
            async with cleanup.begin():
                await cleanup.execute(delete(UserModel).where(UserModel.id == user.id))
