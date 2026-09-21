import uuid

from fastapi import UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..access import master_world, readable_world
from ..files.models import FileModel
from ..filesystem.base import FileSystem
from ..images import ImageNotFoundError, read_image
from ..images.service import purge_owner_revisions, owner_reference, upload_revision
from ..content.constants import ContentKind
from ..content.policy import require_content_update
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
    await refresh_references(
        db,
        world_id,
        ContentKind.NPC,
        reloaded.id,
        reloaded.short_description,
        reloaded.body,
    )
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
        .where(
            NpcModel.world_id == world_id,
            or_(NpcModel.is_draft.is_(False), NpcModel.created_by_id == user.id),
        )
        .order_by(NpcModel.name.asc())
    )
    return list((await db.scalars(stmt)).all())


async def get_npc(
    db: AsyncSession, world_id: uuid.UUID, npc_id: uuid.UUID, user: User
) -> NpcModel:
    await readable_world(db, world_id, user)
    npc = await _get(db, world_id, npc_id)
    if npc is None or (npc.is_draft and npc.created_by_id != user.id):
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
    if npc is None or (npc.is_draft and npc.created_by_id != user.id):
        raise NpcNotFoundException(npc_id)
    require_content_update(npc, data)
    if data.name is not None:
        npc.name = data.name
    if data.title is not None:
        npc.title = data.title
    if data.short_description is not None:
        npc.short_description = data.short_description
    if data.body is not None:
        npc.body = data.body
    if data.tint is not None:
        npc.tint = data.tint
    if data.animal is not None:
        npc.animal = data.animal
    if data.locked is not None:
        npc.locked = data.locked
    if data.is_draft is not None:
        npc.is_draft = data.is_draft
    await db.flush()
    await db.refresh(npc, ["updated_at"])
    await refresh_references(
        db, world_id, ContentKind.NPC, npc.id, npc.short_description, npc.body
    )
    return npc


async def delete_npc(
    db: AsyncSession,
    world_id: uuid.UUID,
    npc_id: uuid.UUID,
    user: User,
    filesystem: FileSystem,
) -> None:
    await master_world(db, world_id, user)
    npc = await _get(db, world_id, npc_id)
    if npc is None or (npc.is_draft and npc.created_by_id != user.id):
        raise NpcNotFoundException(npc_id)
    await purge_owner_revisions(db, filesystem, owner_reference(npc))
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
    if npc is None or (npc.is_draft and npc.created_by_id != user.id):
        raise NpcNotFoundException(npc_id)
    await upload_revision(
        db,
        filesystem,
        upload,
        npc,
        user,
        location_prefix=f"worlds/{world_id}/npcs/{npc_id}",
    )
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
            .where(NpcModel.world_id == world_id, NpcModel.is_draft.is_(False))
        )
    ) or 0
