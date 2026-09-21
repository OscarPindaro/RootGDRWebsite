"""Validated image storage and revision history for image-bearing content."""

import mimetypes
import uuid
from typing import BinaryIO, TypeAlias

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..characters.models import CharacterModel
from ..files.models import FileModel, StorageType
from ..filesystem.base import FileSystem
from ..log import get_logger
from ..npcs.models import NpcModel
from ..places.models import PlaceModel
from ..users.schemas import User
from ..worlds.models import WorldModel
from .exceptions import ImageNotFoundError, ImageValidationError
from .models import ImageOwnerKind, ImageRevisionModel
from .schemas import ImageOwner

logger = get_logger(__name__)

MAX_IMAGE_BYTES = 10 * 1024 * 1024
_CHUNK = 1024 * 1024
_MAGIC: tuple[tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)
_ALLOWED_MIME = {"image/png", "image/jpeg", "image/gif", "image/webp"}
ImageOwnerModel: TypeAlias = WorldModel | CharacterModel | NpcModel | PlaceModel


def sanitize_filename(name: str | None) -> str:
    base = (name or "").replace("\\", "/").split("/")[-1].strip()
    if not base or base in {".", ".."}:
        raise ImageValidationError("The uploaded file has no usable name")
    return base[:255]


def declared_image_mime(filename: str) -> str:
    mime = mimetypes.guess_type(filename)[0]
    if mime not in _ALLOWED_MIME:
        raise ImageValidationError("Only PNG, JPEG, GIF or WebP images are allowed")
    return mime


def sniff_image_mime(header: bytes) -> str | None:
    for signature, mime in _MAGIC:
        if header.startswith(signature):
            return mime
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "image/webp"
    return None


class _BoundedReader:
    def __init__(self, file: BinaryIO, limit: int):
        self._file = file
        self._limit = limit
        self.total = 0

    def read(self, size: int = -1) -> bytes:
        chunk = self._file.read(size)
        self.total += len(chunk)
        if self.total > self._limit:
            raise ImageValidationError(f"Image exceeds the {self._limit} byte limit")
        return chunk


def owner_reference(owner: ImageOwnerModel) -> ImageOwner:
    if isinstance(owner, WorldModel):
        return ImageOwner(
            world_id=owner.id, kind=ImageOwnerKind.WORLD, owner_id=owner.id
        )
    if isinstance(owner, CharacterModel):
        return ImageOwner(
            world_id=owner.world_id,
            kind=ImageOwnerKind.CHARACTER,
            owner_id=owner.id,
        )
    if isinstance(owner, NpcModel):
        return ImageOwner(
            world_id=owner.world_id, kind=ImageOwnerKind.NPC, owner_id=owner.id
        )
    return ImageOwner(
        world_id=owner.world_id, kind=ImageOwnerKind.PLACE, owner_id=owner.id
    )


def current_file_id(owner: ImageOwnerModel) -> uuid.UUID | None:
    if isinstance(owner, WorldModel):
        return owner.image_file_id
    if isinstance(owner, CharacterModel):
        return owner.image_file_id
    if isinstance(owner, NpcModel):
        return owner.image_file_id
    return owner.image_file_id


def set_current_image(owner: ImageOwnerModel, image: FileModel | None) -> None:
    if isinstance(owner, WorldModel):
        owner.image = image
    elif isinstance(owner, CharacterModel):
        owner.image = image
    elif isinstance(owner, NpcModel):
        owner.image = image
    else:
        owner.image = image


async def validate_owner(db: AsyncSession, reference: ImageOwner) -> ImageOwnerModel:
    owner: ImageOwnerModel | None
    if reference.kind == ImageOwnerKind.WORLD:
        if reference.owner_id != reference.world_id:
            raise ImageNotFoundError("The image owner does not belong to this world")
        owner = await db.get(WorldModel, reference.owner_id)
    elif reference.kind == ImageOwnerKind.CHARACTER:
        owner = await db.scalar(
            select(CharacterModel).where(
                CharacterModel.id == reference.owner_id,
                CharacterModel.world_id == reference.world_id,
            )
        )
    elif reference.kind == ImageOwnerKind.NPC:
        owner = await db.scalar(
            select(NpcModel).where(
                NpcModel.id == reference.owner_id,
                NpcModel.world_id == reference.world_id,
            )
        )
    else:
        owner = await db.scalar(
            select(PlaceModel).where(
                PlaceModel.id == reference.owner_id,
                PlaceModel.world_id == reference.world_id,
            )
        )
    if owner is None:
        raise ImageNotFoundError("Image owner not found in this world")
    return owner


async def upload_revision(
    db: AsyncSession,
    filesystem: FileSystem,
    upload: UploadFile,
    owner: ImageOwnerModel,
    uploader: User,
    *,
    location_prefix: str,
) -> ImageRevisionModel:
    """Write a new immutable revision and atomically move the owner's pointer."""
    filename = sanitize_filename(upload.filename)
    declared_image_mime(filename)
    await upload.seek(0)
    if sniff_image_mime(await upload.read(16)) is None:
        await upload.close()
        raise ImageValidationError("The file is not a recognised image")

    file_id = uuid.uuid4()
    location = f"{location_prefix}/{file_id}"
    try:
        await upload.seek(0)
        await filesystem.write_async(
            location, _BoundedReader(upload.file, MAX_IMAGE_BYTES)
        )
        image = FileModel(
            id=file_id,
            name=filename,
            location=location,
            storage_type=StorageType.LOCAL,
        )
        reference = owner_reference(owner)
        revision = ImageRevisionModel(
            world_id=reference.world_id,
            owner_kind=reference.kind,
            owner_id=reference.owner_id,
            file=image,
            uploaded_by_id=uploader.id,
        )
        db.add(revision)
        set_current_image(owner, image)
        await db.flush()
        await db.refresh(revision, ["created_at", "updated_at"])
        return revision
    except ImageValidationError:
        await _discard(filesystem, location)
        raise
    except Exception as exc:
        await _discard(filesystem, location)
        logger.exception("Image upload failed", location=location, error=str(exc))
        raise ImageValidationError("Unable to store the image") from exc
    finally:
        await upload.close()


async def list_revisions(
    db: AsyncSession, reference: ImageOwner
) -> tuple[ImageOwnerModel, list[ImageRevisionModel]]:
    owner = await validate_owner(db, reference)
    revisions = list(
        (
            await db.scalars(
                select(ImageRevisionModel)
                .options(selectinload(ImageRevisionModel.file))
                .where(
                    ImageRevisionModel.world_id == reference.world_id,
                    ImageRevisionModel.owner_kind == reference.kind,
                    ImageRevisionModel.owner_id == reference.owner_id,
                )
                .order_by(
                    ImageRevisionModel.created_at.desc(),
                    ImageRevisionModel.id.desc(),
                )
            )
        ).all()
    )
    return owner, revisions


async def get_revision(
    db: AsyncSession, reference: ImageOwner, revision_id: uuid.UUID
) -> tuple[ImageOwnerModel, ImageRevisionModel]:
    owner = await validate_owner(db, reference)
    revision = await db.scalar(
        select(ImageRevisionModel)
        .options(selectinload(ImageRevisionModel.file))
        .where(
            ImageRevisionModel.id == revision_id,
            ImageRevisionModel.world_id == reference.world_id,
            ImageRevisionModel.owner_kind == reference.kind,
            ImageRevisionModel.owner_id == reference.owner_id,
        )
    )
    if revision is None:
        raise ImageNotFoundError("Image revision not found")
    return owner, revision


async def restore_revision(
    db: AsyncSession, reference: ImageOwner, revision_id: uuid.UUID
) -> ImageRevisionModel:
    owner, revision = await get_revision(db, reference, revision_id)
    set_current_image(owner, revision.file)
    await db.flush()
    return revision


async def clear_current(db: AsyncSession, reference: ImageOwner) -> None:
    owner = await validate_owner(db, reference)
    set_current_image(owner, None)
    await db.flush()


async def delete_revision(
    db: AsyncSession,
    filesystem: FileSystem,
    reference: ImageOwner,
    revision_id: uuid.UUID,
    *,
    replacement_id: uuid.UUID | None = None,
    clear: bool = False,
) -> None:
    owner, revision = await get_revision(db, reference, revision_id)
    is_current = current_file_id(owner) == revision.file_id
    if is_current:
        if replacement_id is not None and clear:
            raise ImageValidationError("Choose either a replacement or clear")
        if replacement_id is not None:
            _, replacement = await get_revision(db, reference, replacement_id)
            if replacement.id == revision.id:
                raise ImageValidationError("Replacement must be another revision")
            set_current_image(owner, replacement.file)
        elif clear:
            set_current_image(owner, None)
        else:
            raise ImageValidationError(
                "Deleting the current revision requires replacement_id or clear=true"
            )
        await db.flush()
    await delete_image(db, filesystem, revision.file)


async def purge_owner_revisions(
    db: AsyncSession, filesystem: FileSystem, reference: ImageOwner
) -> None:
    revisions = list(
        (
            await db.scalars(
                select(ImageRevisionModel)
                .options(selectinload(ImageRevisionModel.file))
                .where(
                    ImageRevisionModel.world_id == reference.world_id,
                    ImageRevisionModel.owner_kind == reference.kind,
                    ImageRevisionModel.owner_id == reference.owner_id,
                )
            )
        ).all()
    )
    for revision in revisions:
        await delete_image(db, filesystem, revision.file)


async def purge_world_revisions(
    db: AsyncSession, filesystem: FileSystem, world_id: uuid.UUID
) -> None:
    revisions = list(
        (
            await db.scalars(
                select(ImageRevisionModel)
                .options(selectinload(ImageRevisionModel.file))
                .where(ImageRevisionModel.world_id == world_id)
            )
        ).all()
    )
    for revision in revisions:
        await delete_image(db, filesystem, revision.file)


async def delete_image(
    db: AsyncSession, filesystem: FileSystem, image: FileModel
) -> None:
    try:
        await filesystem.delete_async(image.location)
    except FileNotFoundError:
        pass
    await db.delete(image)
    await db.flush()


async def read_image(filesystem: FileSystem, image: FileModel) -> bytes:
    return await filesystem.read_async(image.location)


async def _discard(filesystem: FileSystem, location: str) -> None:
    try:
        await filesystem.delete_async(location)
    except Exception:
        logger.warning("Unable to discard image object", location=location)
