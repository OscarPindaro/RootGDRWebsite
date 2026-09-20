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
from .exceptions import NpcNotFoundException
from .models import NpcModel
from .schemas import NpcCreate, NpcUpdate

logger = get_logger(__name__)


async def _get(
    db: AsyncSession, world_id: uuid.UUID, npc_id: uuid.UUID
) -> NpcModel | None:
    return (
        await db.execute(
            select(NpcModel)
            .options(
                selectinload(NpcModel.created_by),
                selectinload(NpcModel.image),
            )
            .where(NpcModel.id == npc_id, NpcModel.world_id == world_id)
        )
    ).scalar_one_or_none()


async def create_npc(
    db: AsyncSession, world_id: uuid.UUID, data: NpcCreate, user: User
) -> NpcModel:
    await master_world(db, world_id, user)
    npc = NpcModel(
        world_id=world_id,
        created_by_id=user.id,
        name=data.name,
        title=data.title,
        short_description=data.short_description,
        body=data.body,
        tint=data.tint,
        animal=data.animal,
        is_draft=data.is_draft,
    )
    db.add(npc)
    await db.flush()
    logger.info("NPC created", world_id=world_id, npc_id=npc.id)
    reloaded = await _get(db, world_id, npc.id)
    assert reloaded is not None
    await refresh_references(db, world_id, ContentKind.NPC, reloaded.id, reloaded.body)
    return reloaded


async def list_npcs(
    db: AsyncSession, world_id: uuid.UUID, user: User
) -> list[NpcModel]:
    await readable_world(db, world_id, user)
    stmt = (
        select(NpcModel)
        .options(
            selectinload(NpcModel.created_by),
            selectinload(NpcModel.image),
        )
        .where(NpcModel.world_id == world_id)
        .order_by(NpcModel.name.asc())
    )
    return list((await db.scalars(stmt)).all())


async def get_npc(
    db: AsyncSession, world_id: uuid.UUID, npc_id: uuid.UUID, user: User
) -> NpcModel:
    await readable_world(db, world_id, user)
    npc = await _get(db, world_id, npc_id)
    if npc is None:
        raise NpcNotFoundException(npc_id)
    return npc


async def update_npc(
    db: AsyncSession,
    world_id: uuid.UUID,
    npc_id: uuid.UUID,
    data: NpcUpdate,
    user: User,
) -> NpcModel:
    await master_world(db, world_id, user)
    npc = await _get(db, world_id, npc_id)
    if npc is None:
        raise NpcNotFoundException(npc_id)
    for field in ("name", "title", "short_description", "body", "tint", "animal"):
        value = getattr(data, field)
        if value is not None:
            setattr(npc, field, value)
    if data.locked is not None:
        npc.locked = data.locked
    if data.is_draft is not None:
        npc.is_draft = data.is_draft
    await db.flush()
    # ``updated_at`` is server-generated; reload it before serialising.
    await db.refresh(npc, ["updated_at"])
    await refresh_references(db, world_id, ContentKind.NPC, npc.id, npc.body)
    return npc


async def delete_npc(
    db: AsyncSession, world_id: uuid.UUID, npc_id: uuid.UUID, user: User
) -> None:
    await master_world(db, world_id, user)
    npc = await _get(db, world_id, npc_id)
    if npc is None:
        raise NpcNotFoundException(npc_id)
    await db.delete(npc)
    await db.flush()


async def upload_npc_image(
    db: AsyncSession,
    world_id: uuid.UUID,
    npc_id: uuid.UUID,
    upload: UploadFile,
    user: User,
    filesystem: FileSystem,
) -> NpcModel:
    await master_world(db, world_id, user)
    npc = await _get(db, world_id, npc_id)
    if npc is None:
        raise NpcNotFoundException(npc_id)
    image = await store_image(
        db,
        filesystem,
        upload,
        location_prefix=f"worlds/{world_id}/npcs/{npc_id}",
        previous=npc.image,
    )
    npc.image = image
    await db.flush()
    await db.refresh(npc, ["updated_at"])
    return npc


async def read_npc_image(
    db: AsyncSession,
    world_id: uuid.UUID,
    npc_id: uuid.UUID,
    user: User,
    filesystem: FileSystem,
) -> tuple[FileModel, bytes]:
    npc = await get_npc(db, world_id, npc_id, user)
    if npc.image is None:
        raise ImageNotFoundError("This NPC does not have an image")
    return npc.image, await read_image(filesystem, npc.image)


async def count_npcs(db: AsyncSession, world_id: uuid.UUID) -> int:
    return (
        await db.scalar(
            select(func.count())
            .select_from(NpcModel)
            .where(NpcModel.world_id == world_id)
        )
    ) or 0
