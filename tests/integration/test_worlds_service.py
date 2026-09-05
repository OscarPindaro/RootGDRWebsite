import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.db.enums import UserRole
from src.backend.users.models import UserModel
from src.backend.users.schemas import User
from src.backend.worlds.exceptions import (
    SharedUserNotFoundException,
    WorldAccessDeniedException,
    WorldNotFoundException,
)
from src.backend.worlds.schemas import WorldCreate, WorldUpdate
from src.backend.worlds.service import create_world, get_world, get_worlds, update_world

pytestmark = pytest.mark.integration


async def _user(db: AsyncSession, name: str) -> User:
    model = UserModel(name=name, email=f"{name}-{uuid.uuid4()}@example.com")
    db.add(model)
    await db.flush()
    return User.model_validate(model)


async def test_world_is_visible_to_its_creator_and_shared_users(
    db_session: AsyncSession,
) -> None:
    creator = await _user(db_session, "creator")
    shared_user = await _user(db_session, "shared")
    outsider = await _user(db_session, "outsider")
    world = await create_world(
        db_session,
        WorldCreate(
            name="The Shattered Coast",
            description="A storm-ravaged archipelago.",
            shared_with=[shared_user.id],
        ),
        creator,
    )

    shared_world = await get_world(db_session, world.id, shared_user)
    worlds, total = await get_worlds(db_session, shared_user)

    assert str(shared_world.id) == str(world.id)
    assert [str(item.id) for item in worlds] == [str(world.id)]
    assert total == 1
    with pytest.raises(WorldNotFoundException):
        await get_world(db_session, world.id, outsider)
    with pytest.raises(WorldAccessDeniedException):
        await update_world(
            db_session,
            world.id,
            WorldUpdate(name="An Unauthorised Change"),
            shared_user,
        )


async def test_world_owner_can_replace_sharing_and_invalid_users_are_rejected(
    db_session: AsyncSession,
) -> None:
    creator = await _user(db_session, "creator")
    shared_user = await _user(db_session, "shared")
    world = await create_world(
        db_session,
        WorldCreate(name="Eldoria", description="An old kingdom."),
        creator,
    )

    updated = await update_world(
        db_session,
        world.id,
        WorldUpdate(
            description="A newly charted kingdom.", shared_with=[shared_user.id]
        ),
        creator,
        include_shared_with=True,
    )

    assert updated.description == "A newly charted kingdom."
    assert [user.id for user in updated.shared_with] == [shared_user.id]
    with pytest.raises(SharedUserNotFoundException):
        await create_world(
            db_session,
            WorldCreate(
                name="Unknown",
                description="Nobody can see it.",
                shared_with=[uuid.uuid4()],
            ),
            creator,
        )


async def test_administrator_can_manage_another_users_world(
    db_session: AsyncSession,
) -> None:
    creator = await _user(db_session, "creator")
    administrator = await _user(db_session, "administrator")
    administrator.role = UserRole.ADMIN
    world = await create_world(
        db_session,
        WorldCreate(name="The Vale", description="A fertile valley."),
        creator,
    )

    updated = await update_world(
        db_session, world.id, WorldUpdate(name="The Verdant Vale"), administrator
    )

    assert updated.name == "The Verdant Vale"
