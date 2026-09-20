import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..access import master_world, readable_world
from ..content.constants import ContentKind
from ..content.references import refresh_references
from ..log import get_logger
from ..users.schemas import User
from .exceptions import SessionNotFoundException
from .models import SessionModel
from .schemas import SessionCreate, SessionUpdate

logger = get_logger(__name__)


def _order():
    """Total order: real date (or creation date), then creation, then id."""
    return (
        func.coalesce(SessionModel.real_date, func.date(SessionModel.created_at)),
        SessionModel.created_at,
        SessionModel.id,
    )


async def _get(
    db: AsyncSession, world_id: uuid.UUID, session_id: uuid.UUID
) -> SessionModel | None:
    return (
        await db.execute(
            select(SessionModel)
            .options(selectinload(SessionModel.created_by))
            .where(SessionModel.id == session_id, SessionModel.world_id == world_id)
        )
    ).scalar_one_or_none()


async def create_session(
    db: AsyncSession, world_id: uuid.UUID, data: SessionCreate, user: User
) -> SessionModel:
    await master_world(db, world_id, user)
    session = SessionModel(
        world_id=world_id,
        created_by_id=user.id,
        title=data.title,
        in_world_date=data.in_world_date,
        real_date=data.real_date,
        short_description=data.short_description,
        body=data.body,
        tint=data.tint,
        is_draft=data.is_draft,
    )
    db.add(session)
    await db.flush()
    logger.info("Session created", world_id=world_id, session_id=session.id)
    reloaded = await _get(db, world_id, session.id)
    assert reloaded is not None
    await refresh_references(
        db, world_id, ContentKind.SESSION, reloaded.id, reloaded.body
    )
    return reloaded


async def list_sessions(
    db: AsyncSession, world_id: uuid.UUID, user: User
) -> list[SessionModel]:
    """All sessions in deterministic order (oldest first)."""
    await readable_world(db, world_id, user)
    return list(
        (
            await db.scalars(
                select(SessionModel)
                .options(selectinload(SessionModel.created_by))
                .where(SessionModel.world_id == world_id)
                .order_by(*_order())
            )
        ).all()
    )


async def get_session(
    db: AsyncSession, world_id: uuid.UUID, session_id: uuid.UUID, user: User
) -> SessionModel:
    await readable_world(db, world_id, user)
    session = await _get(db, world_id, session_id)
    if session is None:
        raise SessionNotFoundException(session_id)
    return session


async def get_neighbours(
    db: AsyncSession, world_id: uuid.UUID, session_id: uuid.UUID, user: User
) -> tuple[tuple[int, SessionModel] | None, tuple[int, SessionModel] | None]:
    """Return ``((number, previous), (number, next))`` for a session."""
    ordered = await list_sessions(db, world_id, user)
    for index, session in enumerate(ordered):
        if session.id == session_id:
            previous = (index, ordered[index - 1]) if index > 0 else None
            following = (
                (index + 2, ordered[index + 1]) if index + 1 < len(ordered) else None
            )
            return previous, following
    return None, None


async def update_session(
    db: AsyncSession,
    world_id: uuid.UUID,
    session_id: uuid.UUID,
    data: SessionUpdate,
    user: User,
) -> SessionModel:
    await master_world(db, world_id, user)
    session = await _get(db, world_id, session_id)
    if session is None:
        raise SessionNotFoundException(session_id)
    for field in ("title", "in_world_date", "short_description", "body", "tint"):
        value = getattr(data, field)
        if value is not None:
            setattr(session, field, value)
    if data.real_date is not None:
        session.real_date = data.real_date
    if data.locked is not None:
        session.locked = data.locked
    if data.is_draft is not None:
        session.is_draft = data.is_draft
    await db.flush()
    # ``updated_at`` is server-generated; reload it before serialising.
    await db.refresh(session, ["updated_at"])
    await refresh_references(
        db, world_id, ContentKind.SESSION, session.id, session.body
    )
    return session


async def delete_session(
    db: AsyncSession, world_id: uuid.UUID, session_id: uuid.UUID, user: User
) -> None:
    await master_world(db, world_id, user)
    session = await _get(db, world_id, session_id)
    if session is None:
        raise SessionNotFoundException(session_id)
    await db.delete(session)
    await db.flush()


async def count_sessions(db: AsyncSession, world_id: uuid.UUID) -> int:
    return (
        await db.scalar(
            select(func.count())
            .select_from(SessionModel)
            .where(SessionModel.world_id == world_id)
        )
    ) or 0


async def recent_sessions(
    db: AsyncSession, world_id: uuid.UUID, limit: int = 4
) -> list[SessionModel]:
    """The most recent sessions, newest first, for the world overview diary."""
    return list(
        (
            await db.scalars(
                select(SessionModel)
                .where(SessionModel.world_id == world_id)
                .order_by(*[column.desc() for column in _order()])
                .limit(limit)
            )
        ).all()
    )
