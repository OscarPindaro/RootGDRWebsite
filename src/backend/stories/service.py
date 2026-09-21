import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..access import master_world, readable_world
from ..content.constants import ContentKind
from ..content.policy import require_content_update
from ..content.references import refresh_references
from ..log import get_logger
from ..sessions.models import SessionModel
from ..users.schemas import User
from .exceptions import StoryNotFoundException
from .models import StoryModel, StoryStatus
from .schemas import StoryCreate, StoryUpdate

logger = get_logger(__name__)


async def _get(
    db: AsyncSession, world_id: uuid.UUID, story_id: uuid.UUID
) -> StoryModel | None:
    return (
        await db.execute(
            select(StoryModel)
            .options(
                selectinload(StoryModel.created_by),
                selectinload(StoryModel.sessions),
            )
            .where(StoryModel.id == story_id, StoryModel.world_id == world_id)
        )
    ).scalar_one_or_none()


async def _resolve_sessions(
    db: AsyncSession, world_id: uuid.UUID, session_ids: list[uuid.UUID]
) -> list[SessionModel]:
    if not session_ids:
        return []
    sessions = list(
        (
            await db.scalars(
                select(SessionModel).where(
                    SessionModel.world_id == world_id,
                    SessionModel.id.in_(session_ids),
                )
            )
        ).all()
    )
    if len(sessions) != len(set(session_ids)):
        raise ValueError("One or more sessions do not belong to this world")
    return sessions


async def create_story(
    db: AsyncSession, world_id: uuid.UUID, data: StoryCreate, user: User
) -> StoryModel:
    await master_world(db, world_id, user)
    story = StoryModel(
        world_id=world_id,
        created_by_id=user.id,
        title=data.title,
        short_description=data.short_description,
        period_label=data.period_label,
        status=data.status,
        tint=data.tint,
        body=data.body,
        is_draft=data.is_draft,
    )
    story.sessions = await _resolve_sessions(db, world_id, data.session_ids)
    db.add(story)
    await db.flush()
    logger.info("Story created", world_id=world_id, story_id=story.id)
    reloaded = await _get(db, world_id, story.id)
    assert reloaded is not None
    await refresh_references(
        db,
        world_id,
        ContentKind.STORY,
        reloaded.id,
        reloaded.short_description,
        reloaded.body,
    )
    return reloaded


async def list_stories(
    db: AsyncSession, world_id: uuid.UUID, user: User
) -> list[StoryModel]:
    """Stories in creation order."""
    await readable_world(db, world_id, user)
    return list(
        (
            await db.scalars(
                select(StoryModel)
                .options(
                    selectinload(StoryModel.created_by),
                    selectinload(StoryModel.sessions),
                )
                .where(
                    StoryModel.world_id == world_id,
                    or_(
                        StoryModel.is_draft.is_(False),
                        StoryModel.created_by_id == user.id,
                    ),
                )
                .order_by(StoryModel.created_at.asc(), StoryModel.id.asc())
            )
        ).all()
    )


async def get_story(
    db: AsyncSession, world_id: uuid.UUID, story_id: uuid.UUID, user: User
) -> StoryModel:
    await readable_world(db, world_id, user)
    story = await _get(db, world_id, story_id)
    if story is None or (story.is_draft and story.created_by_id != user.id):
        raise StoryNotFoundException(story_id)
    return story


async def update_story(
    db: AsyncSession,
    world_id: uuid.UUID,
    story_id: uuid.UUID,
    data: StoryUpdate,
    user: User,
) -> StoryModel:
    await master_world(db, world_id, user)
    story = await _get(db, world_id, story_id)
    if story is None or (story.is_draft and story.created_by_id != user.id):
        raise StoryNotFoundException(story_id)
    require_content_update(story, data)
    if data.title is not None:
        story.title = data.title
    if data.short_description is not None:
        story.short_description = data.short_description
    if "period_label" in data.model_fields_set:
        story.period_label = data.period_label
    if data.status is not None:
        story.status = StoryStatus(data.status)
    if data.tint is not None:
        story.tint = data.tint
    if data.body is not None:
        story.body = data.body
    if data.session_ids is not None:
        story.sessions = await _resolve_sessions(db, world_id, data.session_ids)
    if data.locked is not None:
        story.locked = data.locked
    if data.is_draft is not None:
        story.is_draft = data.is_draft
    await db.flush()
    await db.refresh(story, ["updated_at"])
    await refresh_references(
        db, world_id, ContentKind.STORY, story.id, story.short_description, story.body
    )
    return story


async def delete_story(
    db: AsyncSession, world_id: uuid.UUID, story_id: uuid.UUID, user: User
) -> None:
    await master_world(db, world_id, user)
    story = await _get(db, world_id, story_id)
    if story is None or (story.is_draft and story.created_by_id != user.id):
        raise StoryNotFoundException(story_id)
    await db.delete(story)
    await db.flush()


async def count_stories(db: AsyncSession, world_id: uuid.UUID) -> int:
    return (
        await db.scalar(
            select(func.count())
            .select_from(StoryModel)
            .where(StoryModel.world_id == world_id, StoryModel.is_draft.is_(False))
        )
    ) or 0


async def open_story(db: AsyncSession, world_id: uuid.UUID) -> StoryModel | None:
    """The most recently updated open arc, for the world overview."""
    return (
        await db.execute(
            select(StoryModel)
            .where(
                StoryModel.world_id == world_id,
                StoryModel.status == StoryStatus.OPEN,
                StoryModel.is_draft.is_(False),
            )
            .order_by(StoryModel.updated_at.desc(), StoryModel.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
