import uuid
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.db.enums import UserRole, WorldRole
from src.backend.sessions.schemas import SessionCreate
from src.backend.sessions.service import (
    create_session,
    get_neighbours,
    list_sessions,
    recent_sessions,
)
from src.backend.users.models import UserModel
from src.backend.users.schemas import User
from src.backend.worlds.exceptions import WorldAccessDeniedException
from src.backend.worlds.overview import build_overview
from src.backend.worlds.schemas import WorldCreate, WorldMemberInput
from src.backend.worlds.service import create_world, get_world

pytestmark = pytest.mark.integration


async def _user(db: AsyncSession, name: str, role: UserRole = UserRole.MEMBER) -> User:
    model = UserModel(name=name, email=f"{name}-{uuid.uuid4()}@example.com", role=role)
    db.add(model)
    await db.flush()
    return User.model_validate(model)


async def _world(db: AsyncSession, owner: User, *members: User):
    return await create_world(
        db,
        WorldCreate(
            name="Boscochiaro",
            description="x",
            members=[
                WorldMemberInput(user_id=m.id, role=WorldRole.PLAYER) for m in members
            ],
        ),
        owner,
    )


async def test_previous_next_follow_real_dates(db_session: AsyncSession) -> None:
    master = await _user(db_session, "master")
    world = await _world(db_session, master)
    late = await create_session(
        db_session,
        world.id,
        SessionCreate(
            title="Late", in_world_date="Inverno", real_date=date(2024, 6, 1)
        ),
        master,
    )
    early = await create_session(
        db_session,
        world.id,
        SessionCreate(
            title="Early", in_world_date="Primavera", real_date=date(2024, 1, 1)
        ),
        master,
    )

    ordered = await list_sessions(db_session, world.id, master)
    assert [s.title for s in ordered] == ["Early", "Late"]

    previous, following = await get_neighbours(db_session, world.id, early.id, master)
    assert previous is None
    assert following is not None and following[1].title == "Late"

    previous, following = await get_neighbours(db_session, world.id, late.id, master)
    assert previous is not None and previous[1].title == "Early"
    assert following is None


async def test_sessions_without_a_real_date_use_creation_order(
    db_session: AsyncSession,
) -> None:
    master = await _user(db_session, "master")
    world = await _world(db_session, master)
    first = await create_session(
        db_session, world.id, SessionCreate(title="One", in_world_date="A"), master
    )
    second = await create_session(
        db_session, world.id, SessionCreate(title="Two", in_world_date="B"), master
    )

    ordered = await list_sessions(db_session, world.id, master)
    assert [s.id for s in ordered] == [first.id, second.id]


async def test_only_masters_write_sessions(db_session: AsyncSession) -> None:
    master = await _user(db_session, "master")
    player = await _user(db_session, "player")
    world = await _world(db_session, master, player)

    with pytest.raises(WorldAccessDeniedException):
        await create_session(
            db_session, world.id, SessionCreate(title="X", in_world_date="A"), player
        )


async def test_diary_shows_the_last_four_newest_first(
    db_session: AsyncSession,
) -> None:
    master = await _user(db_session, "master")
    world = await _world(db_session, master)
    for index in range(5):
        await create_session(
            db_session,
            world.id,
            SessionCreate(
                title=f"S{index}",
                in_world_date="X",
                real_date=date(2024, 1, 1 + index),
            ),
            master,
        )

    recent = await recent_sessions(db_session, world.id, 4)
    assert [s.title for s in recent] == ["S4", "S3", "S2", "S1"]

    overview = await build_overview(
        db_session, await get_world(db_session, world.id, master)
    )
    assert [entry.title for entry in overview.diary] == ["S4", "S3", "S2", "S1"]
    assert overview.counts.get("sessioni") == 5
