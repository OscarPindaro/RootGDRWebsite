import mimetypes
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.enums import UserRole
from ..files.models import FileModel, StorageType
from ..filesystem.base import FileSystem
from ..log import get_logger
from ..users.schemas import User
from .exceptions import (
    ImageUploadException,
    SharedUserNotFoundException,
    WorldAccessDeniedException,
    WorldImageNotFoundException,
    WorldNotFoundException,
)
from .models import WorldModel
from .repository import WorldRepository
from .schemas import WorldCreate, WorldUpdate

logger = get_logger(__name__)
MAX_IMAGE_BYTES = 10 * 1024 * 1024


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
    include_shared_with: bool = False,
    include_image: bool = False,
) -> WorldModel:
    world = await WorldRepository(db).get(
        world_id, user.id, _is_admin(user), include_shared_with, include_image
    )
    if world is None:
        raise WorldNotFoundException(world_id)
    return world


async def get_worlds(
    db: AsyncSession,
    user: User,
    page: int = 1,
    page_size: int = 20,
    include_shared_with: bool = False,
) -> tuple[list[WorldModel], int]:
    return await WorldRepository(db).get_page(
        user.id, _is_admin(user), page, page_size, include_shared_with
    )


async def update_world(
    db: AsyncSession,
    world_id: uuid.UUID,
    data: WorldUpdate,
    user: User,
    include_shared_with: bool = False,
) -> WorldModel:
    world = await get_world(db, world_id, user, include_shared_with)
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
    filename = Path(upload.filename or "").name
    mime_type = mimetypes.guess_type(filename)[0]
    if (
        not filename
        or filename in {".", ".."}
        or mime_type is None
        or not mime_type.startswith("image/")
    ):
        await upload.close()
        raise ImageUploadException(
            "Only image files with a recognized extension are allowed"
        )
    if upload.size is not None and upload.size > MAX_IMAGE_BYTES:
        await upload.close()
        raise ImageUploadException(f"Image exceeds the {MAX_IMAGE_BYTES} byte limit")

    file_id = uuid.uuid4()
    location = f"worlds/{world.id}/{file_id}"
    try:
        await upload.seek(0)
        await filesystem.write_async(location, upload.file)
        old_image = world.image
        image = FileModel(
            id=file_id,
            name=filename,
            location=location,
            storage_type=StorageType.LOCAL,
        )
        db.add(image)
        world.image = image
        await db.flush()
        if old_image is not None:
            try:
                await filesystem.delete_async(old_image.location)
            except FileNotFoundError:
                pass
            await db.delete(old_image)
            await db.flush()
    except ImageUploadException:
        raise
    except Exception as exc:
        try:
            await filesystem.delete_async(location)
        except Exception:
            pass
        logger.exception("World image upload failed", world_id=world_id, error=str(exc))
        raise ImageUploadException() from exc
    finally:
        await upload.close()

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
        raise WorldImageNotFoundException(world_id)
    return world.image, await filesystem.read_async(world.image.location)


async def delete_world(db: AsyncSession, world_id: uuid.UUID, user: User) -> None:
    world = await get_world(db, world_id, user)
    _ensure_owner(world, user)
    await WorldRepository(db).delete(world)
    logger.info("World deleted", world_id=world_id, deleted_by_id=user.id)
