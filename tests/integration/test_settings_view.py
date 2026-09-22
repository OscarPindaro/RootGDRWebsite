"""Integration coverage for immediate user-preference persistence."""

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
from src.backend.db.enums import SymbolStyle, UserRole
from src.backend.dependencies import get_db_session
from src.backend.server import create_app
from src.backend.users.models import UserModel
from src.backend.users.schemas import User

pytestmark = pytest.mark.integration


async def test_settings_renders_single_group_and_persists_change(
    app_config: AppConfig, db_manager: DatabaseManager
) -> None:
    app: FastAPI = create_app(app_config)
    email = f"settings-{uuid.uuid4()}@example.com"

    session = db_manager.async_session_maker()
    async with session.begin():
        model = UserModel(name="Settings", email=email, role=UserRole.MEMBER)
        session.add(model)
        await session.flush()
        user_id = model.id
        user = User.model_validate(model)
    await session.close()

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
            page = await client.get("/settings")
            assert page.status_code == 200
            assert page.text.count('type="radio"') == 2
            assert "data-button-group-required" in page.text
            assert 'value="icons" aria-label="Icone" checked required' in page.text
            assert 'data-testid="save-settings"' not in page.text
            # F18: the feedback region is a scoped polite status on the page.
            assert 'id="settings-status" aria-live="polite"' in page.text
            # The form is submittable without JavaScript: a real method/action
            # and a submit control inside <noscript>.
            assert 'method="post"' in page.text
            assert 'action="/settings"' in page.text
            assert "<noscript>" in page.text
            assert 'type="submit"' in page.text

            response = await client.post(
                "/settings",
                data={"symbol_style": "shapes"},
                headers={"HX-Request": "true"},
            )
            assert response.status_code == 200
            # F18: the success feedback is polite, not assertive; the page's
            # `#settings-status` region announces the swap.
            assert 'role="alert"' not in response.text
            assert "Preferenza salvata." in response.text
            # The status fragment echoes the resolved style so Mark.js can flip
            # every mark without a reload; the value is the server's, not the
            # browser's.
            assert 'data-symbol-style="shapes"' in response.text

            # A plain post (no JavaScript) persists too and redirects back to
            # the page, so the next render shows the choice.
            plain = await client.post(
                "/settings",
                data={"symbol_style": "shapes"},
                follow_redirects=False,
            )
            assert plain.status_code == 303
            assert plain.headers["location"] == "/settings"

        verification = db_manager.async_session_maker()
        persisted = await verification.get(UserModel, user_id)
        assert persisted is not None
        assert persisted.symbol_style == SymbolStyle.SHAPES
        await verification.close()
    finally:
        cleanup = db_manager.async_session_maker()
        async with cleanup.begin():
            await cleanup.execute(delete(UserModel).where(UserModel.id == user_id))
        await cleanup.close()
