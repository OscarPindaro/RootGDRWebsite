"""World invites: an email added before the person has an account."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.auth.schemas import InvitationCreate, RegisterRequest
from src.backend.auth.service import create_invitation, register_with_password
from src.backend.config import AppConfig
from src.backend.db.enums import UserRole, WorldRole
from src.backend.users.models import UserModel
from src.backend.users.schemas import User
from src.backend.worlds.invites import (
    apply_pending_invites,
    invite_email,
    list_world_invites,
    revoke_world_invite,
)
from src.backend.worlds.models import WorldMembershipModel
from src.backend.worlds.schemas import WorldCreate
from src.backend.worlds.service import create_world

pytestmark = pytest.mark.integration


async def _user(db: AsyncSession, name: str) -> User:
    model = UserModel(
        name=name, email=f"{name}-{uuid.uuid4()}@example.com", role=UserRole.MEMBER
    )
    db.add(model)
    await db.flush()
    return User.model_validate(model)


async def _world(db: AsyncSession, owner: User) -> uuid.UUID:
    world = await create_world(
        db, WorldCreate(name="Inviti", description="Un mondo con inviti."), owner
    )
    return world.id


async def test_invited_email_joins_the_world_on_registration(
    db_session: AsyncSession, app_config: AppConfig
) -> None:
    owner = await _user(db_session, "owner")
    world_id = await _world(db_session, owner)
    email = f"guest-{uuid.uuid4()}@example.com"
    await invite_email(db_session, world_id, email, WorldRole.PLAYER, owner.id)
    await create_invitation(
        db_session, InvitationCreate(email=email, role=UserRole.MEMBER), owner.id
    )

    guest = await register_with_password(
        db_session,
        RegisterRequest(name="Guest", email=email, password="password123"),
        app_config,
    )

    membership = await db_session.get(WorldMembershipModel, (world_id, guest.id))
    assert membership is not None
    assert membership.role == WorldRole.PLAYER
    assert await list_world_invites(db_session, world_id) == []


async def test_invite_is_upserted_and_revocable(db_session: AsyncSession) -> None:
    owner = await _user(db_session, "owner")
    world_id = await _world(db_session, owner)
    email = f"guest-{uuid.uuid4()}@example.com"

    first = await invite_email(db_session, world_id, email, WorldRole.PLAYER, owner.id)
    second = await invite_email(db_session, world_id, email, WorldRole.MASTER, owner.id)

    assert first.id == second.id
    assert second.role == WorldRole.MASTER

    await revoke_world_invite(db_session, world_id, email)
    assert await list_world_invites(db_session, world_id) == []


async def test_expired_invite_is_not_applied(db_session: AsyncSession) -> None:
    owner = await _user(db_session, "owner")
    world_id = await _world(db_session, owner)
    email = f"guest-{uuid.uuid4()}@example.com"
    await invite_email(
        db_session, world_id, email, WorldRole.PLAYER, owner.id, expire_days=-1
    )

    guest = UserModel(name="Late", email=email, role=UserRole.MEMBER)
    db_session.add(guest)
    await db_session.flush()

    assert await apply_pending_invites(db_session, guest) == 0
    assert await db_session.get(WorldMembershipModel, (world_id, guest.id)) is None
