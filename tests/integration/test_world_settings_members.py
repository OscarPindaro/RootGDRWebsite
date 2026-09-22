"""Integration coverage for the World Settings access surface (F9).

The membership endpoints are HTML/htmx routes now: every mutation returns the
members table fragment instead of a full-page redirect, and the destructive
actions ask a shared confirmation dialog first. These tests exercise the routes
and assert the persisted rows, not just the response markup.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.auth.dependencies import get_current_user
from src.backend.auth.models import InvitationModel
from src.backend.config import AppConfig
from src.backend.db.db import DatabaseManager
from src.backend.db.enums import UserRole, WorldRole
from src.backend.dependencies import get_db_session
from src.backend.server import create_app
from src.backend.users.models import UserModel
from src.backend.users.schemas import User
from src.backend.worlds.models import (
    WorldInviteModel,
    WorldMembershipModel,
    WorldModel,
)

pytestmark = pytest.mark.integration


def _user_schema(user_id: uuid.UUID, name: str, email: str) -> User:
    now = datetime.now(UTC)
    return User(
        id=user_id,
        name=name,
        email=email,
        role=UserRole.MEMBER,
        created_at=now,
        updated_at=now,
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
    app.dependency_overrides[get_current_user] = lambda: user
    return app


@pytest_asyncio.fixture
async def world(db_manager: DatabaseManager) -> AsyncGenerator[dict, None]:
    owner_id = uuid.uuid4()
    member_id = uuid.uuid4()
    outsider_id = uuid.uuid4()
    world_id = uuid.uuid4()
    stamp = uuid.uuid4().hex[:8]
    owner_email = f"owner-{stamp}@example.com"
    member_email = f"member-{stamp}@example.com"
    outsider_email = f"outsider-{stamp}@example.com"

    async with db_manager.async_session_maker() as session:
        async with session.begin():
            session.add_all(
                [
                    UserModel(
                        id=owner_id,
                        name="Owner",
                        email=owner_email,
                        role=UserRole.MEMBER,
                    ),
                    UserModel(
                        id=member_id,
                        name="Membro",
                        email=member_email,
                        role=UserRole.MEMBER,
                    ),
                    UserModel(
                        id=outsider_id,
                        name="Estraneo",
                        email=outsider_email,
                        role=UserRole.MEMBER,
                    ),
                ]
            )
            await session.flush()
            session.add(
                WorldModel(
                    id=world_id,
                    name="Mondo Accessi",
                    description="Un mondo per gli accessi.",
                    created_by_id=owner_id,
                )
            )
            await session.flush()
            session.add_all(
                [
                    WorldMembershipModel(
                        world_id=world_id, user_id=owner_id, role=WorldRole.MASTER
                    ),
                    WorldMembershipModel(
                        world_id=world_id, user_id=member_id, role=WorldRole.PLAYER
                    ),
                ]
            )

    data = {
        "world_id": world_id,
        "owner": _user_schema(owner_id, "Owner", owner_email),
        "member": _user_schema(member_id, "Membro", member_email),
        "outsider": _user_schema(outsider_id, "Estraneo", outsider_email),
        "outsider_email": outsider_email,
        "member_id": member_id,
    }
    yield data

    async with db_manager.async_session_maker() as session:
        async with session.begin():
            await session.execute(
                delete(InvitationModel).where(InvitationModel.invited_by == owner_id)
            )
            await session.execute(delete(WorldModel).where(WorldModel.id == world_id))
            await session.execute(
                delete(UserModel).where(
                    UserModel.id.in_([owner_id, member_id, outsider_id])
                )
            )


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


async def _memberships(db_manager: DatabaseManager, world_id: uuid.UUID) -> dict:
    async with db_manager.async_session_maker() as session:
        rows = await session.execute(
            WorldMembershipModel.__table__.select().where(
                WorldMembershipModel.world_id == world_id
            )
        )
        return {row.user_id: row.role for row in rows}


async def test_adding_an_existing_user_creates_a_membership(
    app_config, db_manager, world
) -> None:
    app = _app(app_config, db_manager, world["owner"])

    response = await _send(
        app,
        "POST",
        f"/worlds/{world['world_id']}/members",
        data={"email": world["outsider_email"], "role": "player"},
    )

    assert response.status_code == 200
    assert "Estraneo" in response.text
    assert "Attivo" in response.text
    roles = await _memberships(db_manager, world["world_id"])
    assert roles[world["outsider"].id] == WorldRole.PLAYER


async def test_inviting_an_unknown_email_leaves_a_pending_invite(
    app_config, db_manager, world
) -> None:
    app = _app(app_config, db_manager, world["owner"])
    email = f"ospite-{uuid.uuid4().hex[:8]}@example.com"

    response = await _send(
        app,
        "POST",
        f"/worlds/{world['world_id']}/members",
        data={"email": email, "role": "master"},
    )

    assert response.status_code == 200
    assert email in response.text
    assert "In attesa" in response.text
    async with db_manager.async_session_maker() as session:
        invite = await session.scalar(
            select(WorldInviteModel).where(
                WorldInviteModel.world_id == world["world_id"],
                WorldInviteModel.email == email,
            )
        )
        assert invite is not None
        assert invite.role == WorldRole.MASTER
        platform = await session.scalar(
            select(InvitationModel).where(InvitationModel.email == email)
        )
        assert platform is not None


async def test_adding_the_same_user_twice_is_idempotent(
    app_config, db_manager, world
) -> None:
    app = _app(app_config, db_manager, world["owner"])
    url = f"/worlds/{world['world_id']}/members"

    await _send(
        app, "POST", url, data={"email": world["outsider_email"], "role": "player"}
    )
    response = await _send(
        app, "POST", url, data={"email": world["outsider_email"], "role": "master"}
    )

    assert response.status_code == 200
    roles = await _memberships(db_manager, world["world_id"])
    # An existing member is not duplicated; the first role stands.
    assert roles[world["outsider"].id] == WorldRole.PLAYER
    assert response.text.count('data-testid="world-member-row"') == 3
    assert "Estraneo è già nel mondo" in response.text


async def test_inviting_the_same_email_twice_upserts_the_role(
    app_config, db_manager, world
) -> None:
    app = _app(app_config, db_manager, world["owner"])
    email = f"ospite-{uuid.uuid4().hex[:8]}@example.com"
    url = f"/worlds/{world['world_id']}/members"

    await _send(app, "POST", url, data={"email": email, "role": "player"})
    await _send(app, "POST", url, data={"email": email, "role": "master"})

    async with db_manager.async_session_maker() as session:
        invites = (
            await session.scalars(
                select(WorldInviteModel).where(
                    WorldInviteModel.world_id == world["world_id"],
                    WorldInviteModel.email == email,
                )
            )
        ).all()
    assert len(invites) == 1
    assert invites[0].role == WorldRole.MASTER


async def test_revoking_a_pending_invite_removes_it(
    app_config, db_manager, world
) -> None:
    app = _app(app_config, db_manager, world["owner"])
    email = f"ospite-{uuid.uuid4().hex[:8]}@example.com"
    await _send(
        app,
        "POST",
        f"/worlds/{world['world_id']}/members",
        data={"email": email, "role": "player"},
    )

    confirm = await _get(app, f"/worlds/{world['world_id']}/invites/{email}/revoke")
    assert confirm.status_code == 200
    assert "hx-delete" in confirm.text
    assert "#world-members" in confirm.text

    response = await _send(
        app, "DELETE", f"/worlds/{world['world_id']}/invites/{email}"
    )
    assert response.status_code == 200
    assert email not in response.text
    async with db_manager.async_session_maker() as session:
        remaining = await session.scalar(
            select(WorldInviteModel).where(
                WorldInviteModel.world_id == world["world_id"],
                WorldInviteModel.email == email,
            )
        )
        assert remaining is None


async def test_removing_a_member_deletes_the_membership(
    app_config, db_manager, world
) -> None:
    app = _app(app_config, db_manager, world["owner"])

    confirm = await _get(
        app,
        f"/worlds/{world['world_id']}/members/{world['member_id']}/remove",
    )
    assert confirm.status_code == 200
    assert "Membro" in confirm.text

    response = await _send(
        app, "DELETE", f"/worlds/{world['world_id']}/members/{world['member_id']}"
    )
    assert response.status_code == 200
    assert "Membro" not in response.text
    roles = await _memberships(db_manager, world["world_id"])
    assert world["member_id"] not in roles
    assert roles[world["owner"].id] == WorldRole.MASTER


async def test_the_owner_cannot_be_removed(app_config, db_manager, world) -> None:
    app = _app(app_config, db_manager, world["owner"])
    owner_id = world["owner"].id

    confirm = await _get(app, f"/worlds/{world['world_id']}/members/{owner_id}/remove")
    assert confirm.status_code == 403

    # Even a forged delete leaves the owner in place: the service re-adds them.
    response = await _send(
        app, "DELETE", f"/worlds/{world['world_id']}/members/{owner_id}"
    )
    assert response.status_code == 200
    roles = await _memberships(db_manager, world["world_id"])
    assert roles[owner_id] == WorldRole.MASTER


async def test_a_non_owner_cannot_manage_members(app_config, db_manager, world) -> None:
    app = _app(app_config, db_manager, world["member"])
    base = f"/worlds/{world['world_id']}"

    dialog = await _get(app, f"{base}/members/dialog")
    assert dialog.status_code == 403
    added = await _send(
        app,
        "POST",
        f"{base}/members",
        data={"email": world["outsider_email"], "role": "player"},
    )
    assert added.status_code == 403
    removed = await _send(app, "DELETE", f"{base}/members/{world['member_id']}")
    assert removed.status_code == 403
    revoke = await _get(app, f"{base}/invites/x@example.com/revoke")
    assert revoke.status_code == 403


async def test_the_dialog_route_returns_the_field_anatomy(
    app_config, db_manager, world
) -> None:
    app = _app(app_config, db_manager, world["owner"])

    response = await _get(app, f"/worlds/{world['world_id']}/members/dialog")

    assert response.status_code == 200
    assert '<label class="field__label" for="email">Email</label>' in response.text
    assert '<label class="field__label" for="role">Ruolo</label>' in response.text
    assert f'hx-post="/worlds/{world["world_id"]}/members"' in response.text
