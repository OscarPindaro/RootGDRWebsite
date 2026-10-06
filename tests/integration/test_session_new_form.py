"""The sessions page's new-draft flow (REQ-0007/T01).

The trigger sends the creating browser's own local ISO date; the route persists
it before the redirect and falls back to Europe/Rome only when the value is
absent, so a session created late at night keeps today's date where it was
created. Ordinary API and import dates never pass through this route.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime

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
from src.backend.sessions import views as session_views
from src.backend.sessions.models import SessionModel
from src.backend.sessions.service import get_session
from src.backend.server import create_app
from src.backend.users.models import UserModel
from src.backend.users.schemas import User
from src.backend.worlds.models import WorldMembershipModel, WorldModel
from src.backend.worlds.schemas import WorldCreate
from src.backend.worlds.service import create_world

pytestmark = pytest.mark.integration


@pytest.fixture()
async def session_app(
    app_config: AppConfig, db_manager: DatabaseManager
) -> AsyncGenerator[tuple[FastAPI, User, uuid.UUID, DatabaseManager], None]:
    email = f"session-form-{uuid.uuid4()}@example.com"
    async with db_manager.async_session_maker() as session:
        async with session.begin():
            model = UserModel(name="Autore", email=email, role=UserRole.MEMBER)
            session.add(model)
            await session.flush()
            user = User.model_validate(model)
            world = await create_world(
                session,
                WorldCreate(name="Boscochiaro", description="x", members=[]),
                user,
            )
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
        yield app, user, world.id, db_manager
    finally:
        async with db_manager.async_session_maker() as cleanup:
            async with cleanup.begin():
                await cleanup.execute(
                    delete(SessionModel).where(SessionModel.world_id == world.id)
                )
                await cleanup.execute(
                    delete(WorldMembershipModel).where(
                        WorldMembershipModel.world_id == world.id
                    )
                )
                await cleanup.execute(
                    delete(WorldModel).where(WorldModel.id == world.id)
                )
                await cleanup.execute(delete(UserModel).where(UserModel.id == user.id))


async def test_the_trigger_persists_the_browser_calendar_date(session_app) -> None:
    app, user, world_id, db_manager = session_app
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        listing = await client.get(f"/worlds/{world_id}/sessions")
        assert listing.status_code == 200
        # The trigger carries the browser's own date, not a render-time value.
        assert 'hx-vals="js:{real_date: localIsoDate()}"' in listing.text

        created = await client.post(
            f"/worlds/{world_id}/sessions/new",
            json={"real_date": "2024-06-01"},
            headers={"HX-Request": "true"},
        )
        assert created.status_code == 204
        session_id = uuid.UUID(
            created.headers["hx-redirect"].split("/sessions/")[1].split("?")[0]
        )

    async with db_manager.async_session_maker() as check:
        stored = await get_session(check, world_id, session_id, user)
    assert stored.real_date == date(2024, 6, 1)


async def test_an_absent_date_falls_back_to_rome(
    session_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, user, world_id, db_manager = session_app
    # 22:30 UTC is already the next day in Europe/Rome: the fallback must use
    # the Rome date, not the server's UTC date.
    instant = datetime(2026, 10, 5, 22, 30, tzinfo=UTC)

    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz)

    monkeypatch.setattr(session_views, "datetime", _FixedDatetime)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        created = await client.post(
            f"/worlds/{world_id}/sessions/new",
            json={},
            headers={"HX-Request": "true"},
        )
        assert created.status_code == 204
        session_id = uuid.UUID(
            created.headers["hx-redirect"].split("/sessions/")[1].split("?")[0]
        )

    async with db_manager.async_session_maker() as check:
        stored = await get_session(check, world_id, session_id, user)
    assert stored.real_date == date(2026, 10, 6)
    assert instant.date() == date(2026, 10, 5)
