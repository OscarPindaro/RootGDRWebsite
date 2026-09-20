import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..access import master_world, readable_world
from ..log import get_logger
from ..users.schemas import User
from .exceptions import PageNotFoundException, PageSlugConflictException
from .models import PageModel
from .schemas import PageCreate, PageUpdate, slugify

logger = get_logger(__name__)


async def _get(
    db: AsyncSession, world_id: uuid.UUID, page_id: uuid.UUID
) -> PageModel | None:
    return (
        await db.execute(
            select(PageModel)
            .options(selectinload(PageModel.created_by))
            .where(PageModel.id == page_id, PageModel.world_id == world_id)
        )
    ).scalar_one_or_none()


async def _slug_taken(
    db: AsyncSession, world_id: uuid.UUID, slug: str, exclude: uuid.UUID | None = None
) -> bool:
    stmt = select(PageModel.id).where(
        PageModel.world_id == world_id, PageModel.slug == slug
    )
    if exclude is not None:
        stmt = stmt.where(PageModel.id != exclude)
    return (await db.scalar(stmt)) is not None


async def create_page(
    db: AsyncSession, world_id: uuid.UUID, data: PageCreate, user: User
) -> PageModel:
    await master_world(db, world_id, user)
    slug = data.slug or slugify(data.title)
    if await _slug_taken(db, world_id, slug):
        raise PageSlugConflictException(slug)
    page = PageModel(
        world_id=world_id,
        created_by_id=user.id,
        title=data.title,
        slug=slug,
        short_description=data.short_description,
        menu_position=data.menu_position,
        tint=data.tint,
        body=data.body,
        is_draft=data.is_draft,
    )
    db.add(page)
    await db.flush()
    logger.info("Page created", world_id=world_id, page_id=page.id, slug=slug)
    reloaded = await _get(db, world_id, page.id)
    assert reloaded is not None
    return reloaded


async def list_pages(
    db: AsyncSession, world_id: uuid.UUID, user: User
) -> list[PageModel]:
    """Pages in menu order."""
    await readable_world(db, world_id, user)
    return list(
        (
            await db.scalars(
                select(PageModel)
                .options(selectinload(PageModel.created_by))
                .where(PageModel.world_id == world_id)
                .order_by(PageModel.menu_position.asc(), PageModel.title.asc())
            )
        ).all()
    )


async def get_page(
    db: AsyncSession, world_id: uuid.UUID, page_id: uuid.UUID, user: User
) -> PageModel:
    await readable_world(db, world_id, user)
    page = await _get(db, world_id, page_id)
    if page is None:
        raise PageNotFoundException(page_id)
    return page


async def get_page_by_slug(
    db: AsyncSession, world_id: uuid.UUID, slug: str, user: User
) -> PageModel:
    await readable_world(db, world_id, user)
    page = (
        await db.execute(
            select(PageModel)
            .options(selectinload(PageModel.created_by))
            .where(PageModel.world_id == world_id, PageModel.slug == slug)
        )
    ).scalar_one_or_none()
    if page is None:
        raise PageNotFoundException(slug)
    return page


async def update_page(
    db: AsyncSession,
    world_id: uuid.UUID,
    page_id: uuid.UUID,
    data: PageUpdate,
    user: User,
) -> PageModel:
    await master_world(db, world_id, user)
    page = await _get(db, world_id, page_id)
    if page is None:
        raise PageNotFoundException(page_id)
    if data.slug is not None and data.slug != page.slug:
        if await _slug_taken(db, world_id, data.slug, exclude=page.id):
            raise PageSlugConflictException(data.slug)
        page.slug = data.slug
    for field in (
        "title",
        "short_description",
        "menu_position",
        "tint",
        "body",
    ):
        value = getattr(data, field)
        if value is not None:
            setattr(page, field, value)
    if data.locked is not None:
        page.locked = data.locked
    if data.is_draft is not None:
        page.is_draft = data.is_draft
    await db.flush()
    return page


async def delete_page(
    db: AsyncSession, world_id: uuid.UUID, page_id: uuid.UUID, user: User
) -> None:
    await master_world(db, world_id, user)
    page = await _get(db, world_id, page_id)
    if page is None:
        raise PageNotFoundException(page_id)
    await db.delete(page)
    await db.flush()


async def count_pages(db: AsyncSession, world_id: uuid.UUID) -> int:
    return (
        await db.scalar(
            select(func.count())
            .select_from(PageModel)
            .where(PageModel.world_id == world_id)
        )
    ) or 0


async def rail_pages(db: AsyncSession, world_id: uuid.UUID) -> list[PageModel]:
    """Published pages in menu order, for the world rail."""
    return list(
        (
            await db.scalars(
                select(PageModel)
                .where(PageModel.world_id == world_id, PageModel.is_draft.is_(False))
                .order_by(PageModel.menu_position.asc(), PageModel.title.asc())
            )
        ).all()
    )
