"""Integration coverage for the Admin surface (F18).

Admin is HTML/htmx: the dashboard renders the users table, the invitation table
is swapped in place after an invite or a revoke, and the revoke asks a shared
confirmation. These tests exercise the routes and assert the persisted rows, and
that the host page declares the assets its htmx fragments need.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.auth.dependencies import get_current_admin_user
from src.backend.auth.models import InvitationModel
from src.backend.config import AppConfig
from src.backend.db.db import DatabaseManager
from src.backend.db.enums import UserRole
from src.backend.dependencies import get_db_session
from src.backend.server import create_app
from src.backend.users.models import UserModel
from src.backend.users.schemas import User

pytestmark = pytest.mark.integration


def _user_schema(user_id: uuid.UUID, name: str, email: str, role: UserRole) -> User:
    now = datetime.now(UTC)
    return User(
        id=user_id,
        name=name,
        email=email,
        role=role,
        created_at=now,
        updated_at=now,
    )


@pytest_asyncio.fixture
async def admin(db_manager: DatabaseManager) -> AsyncGenerator[dict, None]:
    admin_id = uuid.uuid4()
    member_id = uuid.uuid4()
    stamp = uuid.uuid4().hex[:8]
    admin_email = f"admin-{stamp}@example.com"
    member_email = f"member-{stamp}@example.com"
    pending_email = f"pending-{stamp}@example.com"

    async with db_manager.async_session_maker() as session:
        async with session.begin():
            session.add_all(
                [
                    UserModel(
                        id=admin_id,
                        name="Ada",
                        email=admin_email,
                        role=UserRole.ADMIN,
                    ),
                    UserModel(
                        id=member_id,
                        name="Bruno",
                        email=member_email,
                        role=UserRole.MEMBER,
                    ),
                ]
            )
            await session.flush()
            session.add(
                InvitationModel(
                    email=pending_email,
                    role=UserRole.MEMBER,
                    invited_by=admin_id,
                    expires_at=datetime.now(UTC) + timedelta(days=7),
                )
            )

    data = {
        "admin": _user_schema(admin_id, "Ada", admin_email, UserRole.ADMIN),
        "member_email": member_email,
        "pending_email": pending_email,
        "invitation_id": None,
    }
    yield data

    async with db_manager.async_session_maker() as session:
        async with session.begin():
            await session.execute(
                delete(InvitationModel).where(InvitationModel.invited_by == admin_id)
            )
            await session.execute(
                delete(UserModel).where(UserModel.id.in_([admin_id, member_id]))
            )


def _app(app_config: AppConfig, db_manager: DatabaseManager, user: User) -> FastAPI:
    app = create_app(app_config)

    async def _session() -> AsyncGenerator[AsyncSession, None]:
        request_session = db_manager.async_session_maker()
        try:
            async with request_session.begin():
                yield request_session
        finally:
            await request_session.close()

    app.dependency_overrides[get_db_session] = _session
    app.dependency_overrides[get_current_admin_user] = lambda: user
    return app


async def _get(app: FastAPI, path: str):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.get(path, headers={"HX-Request": "true"})


async def _send(app: FastAPI, method: str, path: str, **kwargs):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.request(
            method, path, headers={"HX-Request": "true"}, **kwargs
        )


async def _invitation_id(db_manager: DatabaseManager, email: str) -> int:
    async with db_manager.async_session_maker() as session:
        model = await session.scalar(
            select(InvitationModel).where(InvitationModel.email == email)
        )
        assert model is not None
        return model.id


async def test_the_dashboard_composes_masthead_sections_and_tables(
    app_config, db_manager, admin
) -> None:
    app = _app(app_config, db_manager, admin["admin"])

    response = await _get(app, "/admin/users")

    assert response.status_code == 200
    text = response.text
    assert '<span class="eyebrow">Amministrazione</span>' in text
    assert '<h1 class="display">Utenti</h1>' in text
    assert text.count('<div class="section__head">') == 2
    assert "Persona" in text and "Ruolo" in text and "Stato" in text
    assert "Amministratore" in text and "Attivo" in text
    assert "In attesa" in text
    # The revoke confirmation arrives through htmx: the host must carry its CSS.
    assert "/static/components/common/ConfirmDialog.css" in text
    assert "/static/components/common/HStack.css" in text


async def test_an_empty_invitation_list_shows_the_empty_state(
    app_config, db_manager, admin
) -> None:
    app = _app(app_config, db_manager, admin["admin"])
    # Remove the seeded pending invite so the list is empty.
    async with db_manager.async_session_maker() as session:
        async with session.begin():
            await session.execute(
                delete(InvitationModel).where(
                    InvitationModel.email == admin["pending_email"]
                )
            )

    response = await _get(app, "/admin/users")

    assert response.status_code == 200
    assert "Nessun invito" in response.text
    # Only the users table remains; the invitations section is an empty state.
    assert response.text.count('class="table-wrapper"') == 1


async def test_inviting_returns_the_invitation_table_fragment(
    app_config, db_manager, admin
) -> None:
    app = _app(app_config, db_manager, admin["admin"])
    email = f"nuovo-{uuid.uuid4().hex[:8]}@example.com"

    response = await _send(
        app,
        "POST",
        "/admin/users/invite",
        json={"email": email, "role": "member"},
    )

    assert response.status_code == 200
    # The fragment is the table, not a full page.
    assert "<html" not in response.text
    assert "table-wrapper" in response.text
    assert email in response.text
    assert "In attesa" in response.text
    assert f'hx-target="#confirm-dialog"' in response.text

    async with db_manager.async_session_maker() as session:
        stored = await session.scalar(
            select(InvitationModel).where(InvitationModel.email == email)
        )
        assert stored is not None


async def test_a_duplicate_invite_retargets_the_dialog(
    app_config, db_manager, admin
) -> None:
    app = _app(app_config, db_manager, admin["admin"])

    response = await _send(
        app,
        "POST",
        "/admin/users/invite",
        json={"email": admin["pending_email"], "role": "member"},
    )

    assert response.status_code == 200
    # The dialog comes back in place of the table, so its heading and focus stay.
    assert response.headers["hx-retarget"] == "#invite-dialog"
    assert response.headers["hx-reswap"] == "innerHTML"
    assert "Esiste già un invito" in response.text
    assert "<html" not in response.text


async def test_the_revoke_confirmation_targets_the_table_in_place(
    app_config, db_manager, admin
) -> None:
    app = _app(app_config, db_manager, admin["admin"])
    invitation_id = await _invitation_id(db_manager, admin["pending_email"])

    response = await _get(app, f"/admin/users/invitations/{invitation_id}/revoke")

    assert response.status_code == 200
    assert f'hx-delete="/admin/users/invitations/{invitation_id}"' in response.text
    assert 'hx-target="#invitations-table"' in response.text
    assert 'hx-swap="innerHTML"' in response.text
    assert 'data-dialog-return="invitations-table"' in response.text
    # The request lives on the confirm button, not on the dialog.
    assert response.text.count("hx-delete") == 1


async def test_revoking_removes_the_invitation_and_returns_the_table(
    app_config, db_manager, admin
) -> None:
    app = _app(app_config, db_manager, admin["admin"])
    invitation_id = await _invitation_id(db_manager, admin["pending_email"])

    response = await _send(app, "DELETE", f"/admin/users/invitations/{invitation_id}")

    assert response.status_code == 200
    assert admin["pending_email"] not in response.text
    # The revoked invite was the only one, so the fragment is the empty state.
    assert "Nessun invito" in response.text

    async with db_manager.async_session_maker() as session:
        remaining = await session.scalar(
            select(InvitationModel).where(InvitationModel.id == invitation_id)
        )
        assert remaining is None
