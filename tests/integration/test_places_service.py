import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.db.enums import UserRole, WorldRole
from src.backend.places.exceptions import PlaceNotFoundException
from src.backend.places.schemas import PlaceCreate, PlaceUpdate
from src.backend.places.service import (
    create_place,
    get_place,
    list_places,
    set_current_place,
    update_place,
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


async def test_places_are_master_managed_and_players_read_them(
    db_session: AsyncSession,
) -> None:
    master = await _user(db_session, "master")
    player = await _user(db_session, "player")
    world = await create_world(
        db_session,
        WorldCreate(
            name="Boscochiaro",
            description="A divided wood.",
            members=[WorldMemberInput(user_id=player.id, role=WorldRole.PLAYER)],
        ),
        master,
    )

    with pytest.raises(WorldAccessDeniedException):
        await create_place(db_session, world.id, PlaceCreate(name="Roccianera"), player)

    place = await create_place(
        db_session,
        world.id,
        PlaceCreate(name="Roccianera", tint="p9", shape="rombo"),
        master,
    )
    assert [p.name for p in await list_places(db_session, world.id, player)] == [
        "Roccianera"
    ]

    updated = await update_place(
        db_session, world.id, place.id, PlaceUpdate(shape="esagono"), master
    )
    assert updated.shape == "esagono"


async def test_current_place_feeds_the_overview(db_session: AsyncSession) -> None:
    master = await _user(db_session, "master")
    world = await create_world(
        db_session, WorldCreate(name="Boscochiaro", description="x"), master
    )
    place = await create_place(
        db_session,
        world.id,
        PlaceCreate(
            name="Roccianera", short_description="Città sotterranea.", tint="p9"
        ),
        master,
    )

    await set_current_place(db_session, world.id, place.id, master)
    reloaded = await get_world(db_session, world.id, master)
    overview = await build_overview(db_session, reloaded)

    assert overview.current_place is not None
    assert overview.current_place.title == "Roccianera"
    assert overview.current_place.tint == "p9"
    assert overview.counts.get("luoghi") == 1

    await set_current_place(db_session, world.id, None, master)
    cleared = await build_overview(
        db_session, await get_world(db_session, world.id, master)
    )
    assert cleared.current_place is None


async def test_place_is_scoped_to_its_world(db_session: AsyncSession) -> None:
    master = await _user(db_session, "master")
    world = await create_world(
        db_session, WorldCreate(name="A", description="x"), master
    )
    other = await create_world(
        db_session, WorldCreate(name="B", description="x"), master
    )
    place = await create_place(db_session, world.id, PlaceCreate(name="X"), master)

    with pytest.raises(PlaceNotFoundException):
        await get_place(db_session, other.id, place.id, master)
