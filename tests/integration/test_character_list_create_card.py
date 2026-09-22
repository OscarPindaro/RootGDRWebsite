"""The Character list's collection-create card starts a draft.

F12 removes the masthead plus on Characters and puts the creation affordance in
the grid. Activating it must reuse the draft-first POST route and land in the
one-shot name editor, exactly as the old masthead action did. The card is a real
button, so the keyboard and a screen reader reach it.
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
from src.backend.worlds.schemas import WorldCreate
from src.backend.worlds.service import create_world

pytestmark = pytest.mark.integration


async def test_the_create_card_starts_a_draft_in_name_editing(
    app_config: AppConfig, db_manager: DatabaseManager
) -> None:
    email = f"create-card-{uuid.uuid4()}@example.com"
    session = db_manager.async_session_maker()
    async with session.begin():
        model = UserModel(name="Autore", email=email, role=UserRole.MEMBER)
        session.add(model)
        await session.flush()
        user = User.model_validate(model)
        world = await create_world(
            session, WorldCreate(name="Mondo", description="d"), user
        )
        world_id = world.id
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

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            listing = await client.get(f"/worlds/{world_id}/characters")
            assert listing.status_code == 200
            # The card is a real button carrying the draft-first POST route.
            assert 'aria-label="Nuovo personaggio"' in listing.text
            assert f'hx-post="/worlds/{world_id}/characters/new"' in listing.text
            assert listing.text.count('data-testid="create-character"') == 1
            assert 'class="collection-create"' in listing.text
            # Empty Characters: the card is the collection, not an empty panel
            # with a second action beside it.
            assert "empty-state" not in listing.text
            assert "Nessun personaggio: creane uno per cominciare." in listing.text

            created = await client.post(
                f"/worlds/{world_id}/characters/new",
                json={},
                headers={"HX-Request": "true"},
            )
            assert created.status_code == 204
            location = created.headers["hx-redirect"]
            assert location.endswith("?edit=1"), location

            detail = await client.get(location)
            assert detail.status_code == 200
            # ?edit=1 lands the draft in the name editor.
            assert 'data-auto-edit="true"' in detail.text
    finally:
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
                await cleanup.execute(delete(UserModel).where(UserModel.id == user.id))
