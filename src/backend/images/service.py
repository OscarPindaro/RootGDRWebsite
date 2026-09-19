"""Bounded, validated image storage shared by every feature that carries one.

The rules live here once so worlds, characters, NPCs and places behave the
same: only recognised raster image types, a hard byte limit enforced while the
bytes are read (not from the client-supplied size), a sanitized display name,
and replacement that removes the previous stored object and database row.
"""

import mimetypes
import uuid
from typing import BinaryIO

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from ..files.models import FileModel, StorageType
from ..filesystem.base import FileSystem
from ..log import get_logger
from .exceptions import ImageValidationError

logger = get_logger(__name__)

MAX_IMAGE_BYTES = 10 * 1024 * 1024
_CHUNK = 1024 * 1024

# Raster types only. SVG is deliberately excluded: it can carry script and
# would be served from our own origin.
_MAGIC: tuple[tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)
_ALLOWED_MIME = {"image/png", "image/jpeg", "image/gif", "image/webp"}


def sanitize_filename(name: str | None) -> str:
    """Return a safe display name (basename only, no path, no control chars).

    Both separators are stripped so a Windows-style path cannot smuggle a
    directory component through on a POSIX host.
    """
    base = (name or "").replace("\\", "/").split("/")[-1].strip()
    if not base or base in {".", ".."}:
        raise ImageValidationError("The uploaded file has no usable name")
    return base[:255]


def declared_image_mime(filename: str) -> str:
    """Return the declared image mime type, or reject the upload."""
    mime = mimetypes.guess_type(filename)[0]
    if mime not in _ALLOWED_MIME:
        raise ImageValidationError("Only PNG, JPEG, GIF or WebP images are allowed")
    return mime


def sniff_image_mime(header: bytes) -> str | None:
    """Detect the image type from its magic bytes, or return ``None``."""
    for signature, mime in _MAGIC:
        if header.startswith(signature):
            return mime
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "image/webp"
    return None


class _BoundedReader:
    """A binary reader that raises once ``limit`` bytes have been read.

    ``FileSystem.write_async`` streams from a file-like object, so wrapping the
    upload makes the size limit apply to the bytes actually read rather than to
    the (untrusted) client-supplied ``UploadFile.size``.
    """

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


async def store_image(
    db: AsyncSession,
    filesystem: FileSystem,
    upload: UploadFile,
    *,
    location_prefix: str,
    previous: FileModel | None = None,
) -> FileModel:
    """Validate, store and register an uploaded image, replacing ``previous``.

    ``location_prefix`` is the storage folder for the owner (e.g.
    ``worlds/<id>``); the file key itself is a fresh UUID so the original
    filename never touches the filesystem.
    """
    filename = sanitize_filename(upload.filename)
    declared_image_mime(filename)

    await upload.seek(0)
    header = await upload.read(16)
    if sniff_image_mime(header) is None:
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
        db.add(image)
        await db.flush()
        if previous is not None:
            await delete_image(db, filesystem, previous)
    except ImageValidationError:
        await _discard(filesystem, location)
        raise
    except Exception as exc:
        await _discard(filesystem, location)
        logger.exception("Image upload failed", location=location, error=str(exc))
        raise ImageValidationError("Unable to store the image") from exc
    finally:
        await upload.close()
    return image


async def delete_image(
    db: AsyncSession, filesystem: FileSystem, image: FileModel
) -> None:
    """Remove a stored image and its database record."""
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
        pass
