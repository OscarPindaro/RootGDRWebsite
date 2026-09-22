"""Integration coverage for the command palette's permission filtering.

The palette endpoint is the permission authority: the browser never filters.
These tests exercise the search against a real database and assert that a
reader sees a world's published content, never another author's drafts, and
nothing at all from a world they cannot read.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.db.enums import UserRole, WorldRole
from src.backend.palette import palette
from src.backend.places.schemas import PlaceCreate
from src.backend.places.service import create_place
from src.backend.users.models import UserModel
from src.backend.users.schemas import User
from src.backend.worlds.exceptions import WorldNotFoundException
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


async def _member(db: AsyncSession, world_id, user: User) -> None:
    db.add(
        WorldMembershipModel(world_id=world_id, user_id=user.id, role=WorldRole.PLAYER)
    )
    await db.flush()


async def test_palette_hides_other_authors_drafts_and_keeps_published_content(
    db_session: AsyncSession,
) -> None:
    master = await _user(db_session, "master")
    player = await _user(db_session, "player")
    world = await create_world(
        db_session, WorldCreate(name="Boscochiaro", description="x"), master
    )
    await _member(db_session, world.id, player)
    await create_place(db_session, world.id, PlaceCreate(name="Roccianera"), master)
    await create_place(
        db_session,
        world.id,
        PlaceCreate(name="Roccianera Bozza", is_draft=True),
        master,
    )

    result = await palette(q="Roccia", world_id=world.id, user=player, db=db_session)
    names = [item.name for item in result.data]

    assert "Roccianera" in names
    assert "Roccianera Bozza" not in names


async def test_palette_never_reveals_a_world_the_user_cannot_read(
    db_session: AsyncSession,
) -> None:
    master = await _user(db_session, "master")
    stranger = await _user(db_session, "stranger")
    world = await create_world(
        db_session, WorldCreate(name="Boscochiaro", description="x"), master
    )
    await create_place(db_session, world.id, PlaceCreate(name="Roccianera"), master)

    with pytest.raises(WorldNotFoundException):
        await palette(q="Roccia", world_id=world.id, user=stranger, db=db_session)
