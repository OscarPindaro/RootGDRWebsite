import uuid

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..access import master_world, readable_world
from ..files.models import FileModel
from ..filesystem.base import FileSystem
from ..images import ImageNotFoundError, read_image, store_image
from ..content.constants import ContentKind
from ..content.references import refresh_references
from ..log import get_logger
from ..users.schemas import User
from .exceptions import PlaceNotFoundException
from .models import PlaceModel
from .schemas import PlaceCreate, PlaceUpdate

logger = get_logger(__name__)


async def _get(
    db: AsyncSession, world_id: uuid.UUID, place_id: uuid.UUID
) -> PlaceModel | None:
    return (
        await db.execute(
            select(PlaceModel)
            .options(
                selectinload(PlaceModel.created_by),
                selectinload(PlaceModel.image),
            )
            .where(PlaceModel.id == place_id, PlaceModel.world_id == world_id)
        )
    ).scalar_one_or_none()


async def create_place(
    db: AsyncSession, world_id: uuid.UUID, data: PlaceCreate, user: User
) -> PlaceModel:
    await master_world(db, world_id, user)
    place = PlaceModel(
        world_id=world_id,
        created_by_id=user.id,
        name=data.name,
        short_description=data.short_description,
        body=data.body,
        tint=data.tint,
        shape=data.shape,
        is_draft=data.is_draft,
    )
    db.add(place)
    await db.flush()
    logger.info("Place created", world_id=world_id, place_id=place.id)
    reloaded = await _get(db, world_id, place.id)
    assert reloaded is not None
    await refresh_references(
        db, world_id, ContentKind.PLACE, reloaded.id, reloaded.body
    )
    return reloaded


async def list_places(
    db: AsyncSession, world_id: uuid.UUID, user: User
) -> list[PlaceModel]:
    await readable_world(db, world_id, user)
    stmt = (
        select(PlaceModel)
        .options(
            selectinload(PlaceModel.created_by),
            selectinload(PlaceModel.image),
        )
        .where(PlaceModel.world_id == world_id)
        .order_by(PlaceModel.name.asc())
    )
    return list((await db.scalars(stmt)).all())


async def get_place(
    db: AsyncSession, world_id: uuid.UUID, place_id: uuid.UUID, user: User
) -> PlaceModel:
    await readable_world(db, world_id, user)
    place = await _get(db, world_id, place_id)
    if place is None:
        raise PlaceNotFoundException(place_id)
    return place


async def update_place(
    db: AsyncSession,
    world_id: uuid.UUID,
    place_id: uuid.UUID,
    data: PlaceUpdate,
    user: User,
) -> PlaceModel:
    await master_world(db, world_id, user)
    place = await _get(db, world_id, place_id)
    if place is None:
        raise PlaceNotFoundException(place_id)
    for field in ("name", "short_description", "body", "tint", "shape"):
        value = getattr(data, field)
        if value is not None:
            setattr(place, field, value)
    if data.locked is not None:
        place.locked = data.locked
    if data.is_draft is not None:
        place.is_draft = data.is_draft
    await db.flush()
    # ``updated_at`` is server-generated; reload it before serialising.
    await db.refresh(place, ["updated_at"])
    await refresh_references(db, world_id, ContentKind.PLACE, place.id, place.body)
    return place


async def delete_place(
    db: AsyncSession, world_id: uuid.UUID, place_id: uuid.UUID, user: User
) -> None:
    await master_world(db, world_id, user)
    place = await _get(db, world_id, place_id)
    if place is None:
        raise PlaceNotFoundException(place_id)
    await db.delete(place)
    await db.flush()


async def upload_place_image(
    db: AsyncSession,
    world_id: uuid.UUID,
    place_id: uuid.UUID,
    upload: UploadFile,
    user: User,
    filesystem: FileSystem,
) -> PlaceModel:
    await master_world(db, world_id, user)
    place = await _get(db, world_id, place_id)
    if place is None:
        raise PlaceNotFoundException(place_id)
    image = await store_image(
        db,
        filesystem,
        upload,
        location_prefix=f"worlds/{world_id}/places/{place_id}",
        previous=place.image,
    )
    place.image = image
    await db.flush()
    await db.refresh(place, ["updated_at"])
    return place


async def read_place_image(
    db: AsyncSession,
    world_id: uuid.UUID,
    place_id: uuid.UUID,
    user: User,
    filesystem: FileSystem,
) -> tuple[FileModel, bytes]:
    place = await get_place(db, world_id, place_id, user)
    if place.image is None:
        raise ImageNotFoundError("This place does not have an image")
    return place.image, await read_image(filesystem, place.image)


async def count_places(db: AsyncSession, world_id: uuid.UUID) -> int:
    return (
        await db.scalar(
            select(func.count())
            .select_from(PlaceModel)
            .where(PlaceModel.world_id == world_id)
        )
    ) or 0


async def set_current_place(
    db: AsyncSession, world_id: uuid.UUID, place_id: uuid.UUID | None, user: User
) -> None:
    """Mark the clearing the party is currently in (master only)."""
    world = await master_world(db, world_id, user)
    if place_id is not None:
        place = await _get(db, world_id, place_id)
        if place is None:
            raise PlaceNotFoundException(place_id)
    world.current_place_id = place_id
    await db.flush()
