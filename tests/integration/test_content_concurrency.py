import uuid

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.characters.models import CharacterModel
from src.backend.characters.schemas import CharacterCreate, CharacterUpdate
from src.backend.characters.service import create_character, update_character
from src.backend.concurrency import VersionConflictException
from src.backend.content.policy import ContentLockedException
from src.backend.db.db import DatabaseManager
from src.backend.db.enums import UserRole
from src.backend.dependencies import get_db_session
from src.backend.npcs.schemas import NpcCreate, NpcUpdate
from src.backend.npcs.service import create_npc, update_npc
from src.backend.pages.schemas import PageCreate, PageUpdate
from src.backend.pages.service import create_page, update_page
from src.backend.places.schemas import PlaceCreate, PlaceUpdate
from src.backend.places.service import create_place, update_place
from src.backend.sessions.schemas import SessionCreate, SessionUpdate
from src.backend.sessions.service import create_session, update_session
from src.backend.stories.schemas import StoryCreate, StoryUpdate
from src.backend.stories.service import create_story, update_story
from src.backend.users.models import UserModel
from src.backend.users.schemas import User
from src.backend.worlds.models import WorldModel
from src.backend.worlds.schemas import WorldCreate
from src.backend.worlds.service import create_world

pytestmark = pytest.mark.integration


async def _master(db: AsyncSession) -> User:
    model = UserModel(
        name="lock-master",
        email=f"lock-master-{uuid.uuid4()}@example.com",
        role=UserRole.MEMBER,
    )
    db.add(model)
    await db.flush()
    return User.model_validate(model)


async def test_every_content_service_rejects_edits_until_authorized_unlock(
    db_session: AsyncSession,
) -> None:
    master = await _master(db_session)
    world = await create_world(
        db_session, WorldCreate(name="Locks", description="Contract"), master
    )

    character = await create_character(
        db_session, world.id, CharacterCreate(name="Character"), master
    )
    await update_character(
        db_session,
        world.id,
        character.id,
        CharacterUpdate(locked=True, expected_version=character.version),
        master,
    )
    with pytest.raises(ContentLockedException):
        await update_character(
            db_session,
            world.id,
            character.id,
            CharacterUpdate(name="Blocked", expected_version=character.version),
            master,
        )
    await update_character(
        db_session,
        world.id,
        character.id,
        CharacterUpdate(locked=False, expected_version=character.version),
        master,
    )

    npc = await create_npc(db_session, world.id, NpcCreate(name="NPC"), master)
    await update_npc(
        db_session,
        world.id,
        npc.id,
        NpcUpdate(locked=True, expected_version=npc.version),
        master,
    )
    with pytest.raises(ContentLockedException):
        await update_npc(
            db_session,
            world.id,
            npc.id,
            NpcUpdate(name="Blocked", expected_version=npc.version),
            master,
        )
    await update_npc(
        db_session,
        world.id,
        npc.id,
        NpcUpdate(locked=False, expected_version=npc.version),
        master,
    )

    place = await create_place(db_session, world.id, PlaceCreate(name="Place"), master)
    await update_place(
        db_session,
        world.id,
        place.id,
        PlaceUpdate(locked=True, expected_version=place.version),
        master,
    )
    with pytest.raises(ContentLockedException):
        await update_place(
            db_session,
            world.id,
            place.id,
            PlaceUpdate(name="Blocked", expected_version=place.version),
            master,
        )
    await update_place(
        db_session,
        world.id,
        place.id,
        PlaceUpdate(locked=False, expected_version=place.version),
        master,
    )

    session = await create_session(
        db_session,
        world.id,
        SessionCreate(title="Session", in_world_date="Today"),
        master,
    )
    await update_session(
        db_session,
        world.id,
        session.id,
        SessionUpdate(locked=True, expected_version=session.version),
        master,
    )
    with pytest.raises(ContentLockedException):
        await update_session(
            db_session,
            world.id,
            session.id,
            SessionUpdate(title="Blocked", expected_version=session.version),
            master,
        )
    await update_session(
        db_session,
        world.id,
        session.id,
        SessionUpdate(locked=False, expected_version=session.version),
        master,
    )

    story = await create_story(db_session, world.id, StoryCreate(title="Story"), master)
    await update_story(
        db_session,
        world.id,
        story.id,
        StoryUpdate(locked=True, expected_version=story.version),
        master,
    )
    with pytest.raises(ContentLockedException):
        await update_story(
            db_session,
            world.id,
            story.id,
            StoryUpdate(title="Blocked", expected_version=story.version),
            master,
        )
    await update_story(
        db_session,
        world.id,
        story.id,
        StoryUpdate(locked=False, expected_version=story.version),
        master,
    )

    page = await create_page(db_session, world.id, PageCreate(title="Page"), master)
    await update_page(
        db_session,
        world.id,
        page.id,
        PageUpdate(locked=True, expected_version=page.version),
        master,
    )
    with pytest.raises(ContentLockedException):
        await update_page(
            db_session,
            world.id,
            page.id,
            PageUpdate(title="Blocked", expected_version=page.version),
            master,
        )
    await update_page(
        db_session,
        world.id,
        page.id,
        PageUpdate(locked=False, expected_version=page.version),
        master,
    )


async def test_true_two_session_race_becomes_typed_409(
    db_manager: DatabaseManager,
) -> None:
    seed = db_manager.async_session_maker()
    async with seed.begin():
        user = UserModel(
            name="race-master",
            email=f"race-master-{uuid.uuid4()}@example.com",
            role=UserRole.MEMBER,
        )
        seed.add(user)
        await seed.flush()
        world = WorldModel(name="Race", description="Race", created_by_id=user.id)
        seed.add(world)
        await seed.flush()
        character = CharacterModel(
            world_id=world.id,
            owner_id=user.id,
            name="Contested",
        )
        seed.add(character)
        await seed.flush()
        user_id = user.id
        world_id = world.id
        character_id = character.id
    await seed.close()

    first = db_manager.async_session_maker()
    request_scope = get_db_session(db_manager)
    second = await anext(request_scope)
    async with first.begin():
        first_copy = await first.get(CharacterModel, character_id)
        second_copy = await second.get(CharacterModel, character_id)
        assert first_copy is not None and second_copy is not None
        first_copy.body = "first"
        second_copy.body = "second"

    with pytest.raises(VersionConflictException) as conflict:
        await anext(request_scope)
    assert conflict.value.status_code == 409
    await first.close()

    cleanup = db_manager.async_session_maker()
    async with cleanup.begin():
        await cleanup.execute(delete(WorldModel).where(WorldModel.id == world_id))
        await cleanup.execute(delete(UserModel).where(UserModel.id == user_id))
    await cleanup.close()
