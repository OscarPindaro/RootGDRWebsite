import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.db.enums import UserRole, WorldRole
from src.backend.users.models import UserModel
from src.backend.users.schemas import User
from src.backend.worlds.exceptions import (
    SharedUserNotFoundException,
    WorldAccessDeniedException,
    WorldNotFoundException,
)
from src.backend.worlds.schemas import WorldCreate, WorldMemberInput, WorldUpdate
from src.backend.worlds.service import (
    create_world,
    get_world,
    get_world_role,
    get_worlds,
    set_members,
    update_world,
)

pytestmark = pytest.mark.integration


async def _user(db: AsyncSession, name: str, role: UserRole = UserRole.MEMBER) -> User:
    model = UserModel(name=name, email=f"{name}-{uuid.uuid4()}@example.com", role=role)
    db.add(model)
    await db.flush()
    return User.model_validate(model)


async def test_world_is_visible_to_its_creator_and_members(
    db_session: AsyncSession,
) -> None:
    creator = await _user(db_session, "creator")
    member = await _user(db_session, "member")
    outsider = await _user(db_session, "outsider")
    world = await create_world(
        db_session,
        WorldCreate(
            name="The Shattered Coast",
            description="A storm-ravaged archipelago.",
            members=[WorldMemberInput(user_id=member.id, role=WorldRole.PLAYER)],
        ),
        creator,
    )

    member_world = await get_world(db_session, world.id, member)
    worlds, total = await get_worlds(db_session, member)

    assert str(member_world.id) == str(world.id)
    assert [str(item.id) for item in worlds] == [str(world.id)]
    assert total == 1
    with pytest.raises(WorldNotFoundException):
        await get_world(db_session, world.id, outsider)
    with pytest.raises(WorldAccessDeniedException):
        await update_world(
            db_session,
            world.id,
            WorldUpdate(name="An Unauthorised Change"),
            member,
        )


async def test_owner_is_always_a_master_and_cannot_be_demoted(
    db_session: AsyncSession,
) -> None:
    creator = await _user(db_session, "creator")
    other = await _user(db_session, "other")
    world = await create_world(
        db_session,
        WorldCreate(
            name="Eldoria",
            description="An old kingdom.",
            # Try to demote the owner; the owner must win.
            members=[WorldMemberInput(user_id=creator.id, role=WorldRole.PLAYER)],
        ),
        creator,
    )

    assert await get_world_role(db_session, world, creator) == WorldRole.MASTER

    updated = await update_world(
        db_session,
        world.id,
        WorldUpdate(
            description="A newly charted kingdom.",
            members=[WorldMemberInput(user_id=other.id, role=WorldRole.MASTER)],
        ),
        creator,
        include_members=True,
    )

    assert updated.description == "A newly charted kingdom."
    assert {m.user.id: m.role for m in updated.memberships} == {
        creator.id: WorldRole.MASTER,
        other.id: WorldRole.MASTER,
    }


async def test_invalid_members_are_rejected(db_session: AsyncSession) -> None:
    creator = await _user(db_session, "creator")

    with pytest.raises(SharedUserNotFoundException):
        await create_world(
            db_session,
            WorldCreate(
                name="Unknown",
                description="Nobody can see it.",
                members=[WorldMemberInput(user_id=uuid.uuid4())],
            ),
            creator,
        )


async def test_administrator_can_manage_another_users_world(
    db_session: AsyncSession,
) -> None:
    creator = await _user(db_session, "creator")
    administrator = await _user(db_session, "administrator", UserRole.ADMIN)
    world = await create_world(
        db_session,
        WorldCreate(name="The Vale", description="A fertile valley."),
        creator,
    )

    updated = await update_world(
        db_session, world.id, WorldUpdate(name="The Verdant Vale"), administrator
    )

    assert updated.name == "The Verdant Vale"


async def test_owner_can_add_and_remove_members(db_session: AsyncSession) -> None:
    owner = await _user(db_session, "owner")
    player = await _user(db_session, "player")
    world = await create_world(
        db_session,
        WorldCreate(name="Boscochiaro", description="A divided wood."),
        owner,
    )

    added = await set_members(
        db_session,
        world.id,
        [WorldMemberInput(user_id=player.id, role=WorldRole.PLAYER)],
        owner,
    )
    assert {m.user_id: m.role for m in added.memberships} == {
        owner.id: WorldRole.MASTER,
        player.id: WorldRole.PLAYER,
    }
    assert await get_world_role(db_session, added, player) == WorldRole.PLAYER

    # A player can read the world but cannot change its membership.
    with pytest.raises(WorldAccessDeniedException):
        await set_members(db_session, world.id, [], player)

    removed = await set_members(
        db_session,
        world.id,
        [WorldMemberInput(user_id=owner.id, role=WorldRole.MASTER)],
        owner,
    )
    assert [m.user_id for m in removed.memberships] == [owner.id]

    # Once removed, the world is no longer visible to the former player.
    with pytest.raises(WorldNotFoundException):
        await set_members(db_session, world.id, [], player)
