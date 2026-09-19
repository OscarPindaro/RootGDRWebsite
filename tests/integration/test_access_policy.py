import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.access import master_world, owner_world, readable_world
from src.backend.db.enums import UserRole, WorldRole
from src.backend.users.models import UserModel
from src.backend.users.schemas import User
from src.backend.worlds.exceptions import (
    WorldAccessDeniedException,
    WorldNotFoundException,
)
from src.backend.worlds.schemas import WorldCreate, WorldMemberInput
from src.backend.worlds.service import create_world

pytestmark = pytest.mark.integration


async def _user(db: AsyncSession, name: str, role: UserRole = UserRole.MEMBER) -> User:
    model = UserModel(name=name, email=f"{name}-{uuid.uuid4()}@example.com", role=role)
    db.add(model)
    await db.flush()
    return User.model_validate(model)


async def test_readable_master_and_owner_boundaries(db_session: AsyncSession) -> None:
    owner = await _user(db_session, "owner")
    master = await _user(db_session, "master")
    player = await _user(db_session, "player")
    outsider = await _user(db_session, "outsider")
    admin = await _user(db_session, "admin", UserRole.ADMIN)

    world = await create_world(
        db_session,
        WorldCreate(
            name="Boscochiaro",
            description="A divided wood.",
            members=[
                WorldMemberInput(user_id=master.id, role=WorldRole.MASTER),
                WorldMemberInput(user_id=player.id, role=WorldRole.PLAYER),
            ],
        ),
        owner,
    )

    # readable: owner, master, player and site admin
    for user in (owner, master, player, admin):
        assert (await readable_world(db_session, world.id, user)).id == world.id

    # outsider sees a 404, never a 403 — the world's existence is not revealed
    with pytest.raises(WorldNotFoundException):
        await readable_world(db_session, world.id, outsider)

    # master-required: owner and master pass, player and outsider do not
    assert (await master_world(db_session, world.id, owner)).id == world.id
    assert (await master_world(db_session, world.id, master)).id == world.id
    with pytest.raises(WorldAccessDeniedException):
        await master_world(db_session, world.id, player)
    with pytest.raises(WorldNotFoundException):
        await master_world(db_session, world.id, outsider)

    # owner-only: only the owner (and a site admin) pass
    assert (await owner_world(db_session, world.id, owner)).id == world.id
    assert (await owner_world(db_session, world.id, admin)).id == world.id
    with pytest.raises(WorldAccessDeniedException):
        await owner_world(db_session, world.id, master)


async def test_cross_world_ids_do_not_leak(db_session: AsyncSession) -> None:
    owner_a = await _user(db_session, "owner-a")
    owner_b = await _user(db_session, "owner-b")
    world_a = await create_world(
        db_session,
        WorldCreate(name="World A", description="First."),
        owner_a,
    )
    await create_world(
        db_session,
        WorldCreate(name="World B", description="Second."),
        owner_b,
    )

    # owner-b cannot read, master or own world A
    with pytest.raises(WorldNotFoundException):
        await readable_world(db_session, world_a.id, owner_b)
    with pytest.raises(WorldNotFoundException):
        await master_world(db_session, world_a.id, owner_b)
    with pytest.raises(WorldNotFoundException):
        await owner_world(db_session, world_a.id, owner_b)
