import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.db.enums import UserRole, WorldRole
from src.backend.sessions.schemas import SessionCreate
from src.backend.sessions.service import create_session
from src.backend.stories.exceptions import StoryNotFoundException
from src.backend.stories.models import StoryStatus
from src.backend.stories.schemas import StoryCreate, StoryUpdate
from src.backend.stories.service import (
    create_story,
    get_story,
    list_stories,
    open_story,
    update_story,
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


async def test_story_links_sessions_and_is_master_managed(
    db_session: AsyncSession,
) -> None:
    master = await _user(db_session, "master")
    player = await _user(db_session, "player")
    world = await create_world(
        db_session,
        WorldCreate(
            name="Boscochiaro",
            description="x",
            members=[WorldMemberInput(user_id=player.id, role=WorldRole.PLAYER)],
        ),
        master,
    )
    session = await create_session(
        db_session,
        world.id,
        SessionCreate(title="L'inverno dei corvi", in_world_date="Inverno"),
        master,
    )

    with pytest.raises(WorldAccessDeniedException):
        await create_story(db_session, world.id, StoryCreate(title="X"), player)

    story = await create_story(
        db_session,
        world.id,
        StoryCreate(
            title="L'inverno dei corvi",
            short_description="Il gelo chiude il fiume.",
            period_label="Inverno, 4° anno",
            session_ids=[session.id],
        ),
        master,
    )
    assert [s.id for s in story.sessions] == [session.id]
    assert [s.title for s in await list_stories(db_session, world.id, player)] == [
        "L'inverno dei corvi"
    ]

    closed = await update_story(
        db_session,
        world.id,
        story.id,
        StoryUpdate(status=StoryStatus.CLOSED, session_ids=[]),
        master,
    )
    assert closed.status == StoryStatus.CLOSED
    assert closed.sessions == []


async def test_open_story_feeds_the_overview(db_session: AsyncSession) -> None:
    master = await _user(db_session, "master")
    world = await create_world(
        db_session, WorldCreate(name="Boscochiaro", description="x"), master
    )
    await create_story(
        db_session,
        world.id,
        StoryCreate(title="Chiusa", status=StoryStatus.CLOSED, tint="p3"),
        master,
    )
    await create_story(
        db_session,
        world.id,
        StoryCreate(
            title="Aperta",
            status=StoryStatus.OPEN,
            tint="p8",
            short_description="In corso.",
        ),
        master,
    )

    assert (await open_story(db_session, world.id)).title == "Aperta"
    overview = await build_overview(
        db_session, await get_world(db_session, world.id, master)
    )
    assert overview.open_story is not None
    assert overview.open_story.title == "Aperta"
    assert overview.open_story.tint == "p8"
    assert overview.counts.get("storie") == 2


async def test_story_is_scoped_to_its_world(db_session: AsyncSession) -> None:
    master = await _user(db_session, "master")
    world = await create_world(
        db_session, WorldCreate(name="A", description="x"), master
    )
    other = await create_world(
        db_session, WorldCreate(name="B", description="x"), master
    )
    story = await create_story(db_session, world.id, StoryCreate(title="X"), master)

    with pytest.raises(StoryNotFoundException):
        await get_story(db_session, other.id, story.id, master)
