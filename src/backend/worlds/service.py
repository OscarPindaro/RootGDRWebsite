import uuid

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.enums import UserRole, WorldRole
from ..files.models import FileModel
from ..filesystem.base import FileSystem
from ..images import ImageNotFoundError, read_image, store_image
from ..log import get_logger
from ..users.schemas import User
from .exceptions import (
    SharedUserNotFoundException,
    WorldAccessDeniedException,
    WorldNotFoundException,
)
from .models import WorldModel
from .repository import WorldRepository
from .schemas import WorldCreate, WorldUpdate

logger = get_logger(__name__)


def _is_admin(user: User) -> bool:
    return user.role == UserRole.ADMIN


def _ensure_owner(world: WorldModel, user: User) -> None:
    if not _is_admin(user) and world.created_by_id != user.id:
        raise WorldAccessDeniedException(world.id)


async def create_world(db: AsyncSession, data: WorldCreate, user: User) -> WorldModel:
    try:
        world = await WorldRepository(db).create(data, user.id)
    except ValueError as exc:
        raise SharedUserNotFoundException() from exc
    logger.info("World created", world_id=world.id, created_by_id=user.id)
    return world


async def get_world(
    db: AsyncSession,
    world_id: uuid.UUID,
    user: User,
    include_members: bool = False,
    include_image: bool = False,
) -> WorldModel:
    world = await WorldRepository(db).get(
        world_id, user.id, _is_admin(user), include_members, include_image
    )
    if world is None:
        raise WorldNotFoundException(world_id)
    return world


async def get_worlds(
    db: AsyncSession,
    user: User,
    page: int = 1,
    page_size: int = 20,
    include_members: bool = False,
) -> tuple[list[WorldModel], int]:
    return await WorldRepository(db).get_page(
        user.id, _is_admin(user), page, page_size, include_members
    )


async def get_world_role(db: AsyncSession, world: WorldModel, user: User) -> WorldRole:
    """Return the user's effective role in a world they can access."""
    if _is_admin(user) or world.created_by_id == user.id:
        return WorldRole.MASTER
    membership = await WorldRepository(db).get_membership(world.id, user.id)
    return membership.role if membership else WorldRole.PLAYER


async def is_master(db: AsyncSession, world: WorldModel, user: User) -> bool:
    return await get_world_role(db, world, user) == WorldRole.MASTER


async def update_world(
    db: AsyncSession,
    world_id: uuid.UUID,
    data: WorldUpdate,
    user: User,
    include_members: bool = False,
) -> WorldModel:
    world = await get_world(db, world_id, user, include_members)
    _ensure_owner(world, user)
    try:
        updated = await WorldRepository(db).update(world, data)
    except ValueError as exc:
        raise SharedUserNotFoundException() from exc
    logger.info("World updated", world_id=world_id, updated_by_id=user.id)
    return updated


async def upload_world_image(
    db: AsyncSession,
    world_id: uuid.UUID,
    upload: UploadFile,
    user: User,
    filesystem: FileSystem,
) -> WorldModel:
    try:
        world = await get_world(db, world_id, user, include_image=True)
        _ensure_owner(world, user)
    except Exception:
        await upload.close()
        raise
    image = await store_image(
        db,
        filesystem,
        upload,
        location_prefix=f"worlds/{world.id}",
        previous=world.image,
    )
    world.image = image
    await db.flush()
    logger.info("World image uploaded", world_id=world_id, uploaded_by_id=user.id)
    return world


async def read_world_image(
    db: AsyncSession,
    world_id: uuid.UUID,
    user: User,
    filesystem: FileSystem,
) -> tuple[FileModel, bytes]:
    world = await get_world(db, world_id, user, include_image=True)
    if world.image is None:
        raise ImageNotFoundError("This world does not have an image")
    return world.image, await read_image(filesystem, world.image)


async def delete_world(db: AsyncSession, world_id: uuid.UUID, user: User) -> None:
    world = await get_world(db, world_id, user)
    _ensure_owner(world, user)
    await WorldRepository(db).delete(world)
    logger.info("World deleted", world_id=world_id, deleted_by_id=user.id)
