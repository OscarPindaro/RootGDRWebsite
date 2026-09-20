import uuid

from fastapi import UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..access import is_admin, readable_world
from ..files.models import FileModel
from ..filesystem.base import FileSystem
from ..images import ImageNotFoundError, read_image, store_image
from ..content.constants import ContentKind
from ..content.policy import require_content_update
from ..content.references import refresh_references
from ..log import get_logger
from ..users.models import UserModel
from ..users.schemas import User
from ..worlds.models import WorldModel
from ..worlds.service import is_master
from .exceptions import CharacterAccessDeniedException, CharacterNotFoundException
from .models import CharacterModel
from .schemas import CharacterCreate, CharacterUpdate

logger = get_logger(__name__)


def _draft_visible(user: User):
    """Drafts are visible only to their author."""
    return or_(CharacterModel.is_draft.is_(False), CharacterModel.owner_id == user.id)


async def _get(
    db: AsyncSession, world_id: uuid.UUID, character_id: uuid.UUID
) -> CharacterModel | None:
    return (
        await db.execute(
            select(CharacterModel)
            .options(
                selectinload(CharacterModel.owner),
                selectinload(CharacterModel.image),
            )
            .where(
                CharacterModel.id == character_id,
                CharacterModel.world_id == world_id,
            )
        )
    ).scalar_one_or_none()


async def _require_manage(
    db: AsyncSession, world: WorldModel, character: CharacterModel, user: User
) -> None:
    if character.owner_id == user.id or await is_master(db, world, user):
        return
    raise CharacterAccessDeniedException()


async def create_character(
    db: AsyncSession, world_id: uuid.UUID, data: CharacterCreate, user: User
) -> CharacterModel:
    world = await readable_world(db, world_id, user)
    owner_id = data.owner_id or user.id
    if owner_id != user.id and not await is_master(db, world, user):
        raise CharacterAccessDeniedException()
    character = CharacterModel(
        world_id=world_id,
        owner_id=owner_id,
        name=data.name,
        title=data.title,
        short_description=data.short_description,
        body=data.body,
        tint=data.tint,
        animal=data.animal,
        is_draft=data.is_draft,
    )
    db.add(character)
    await db.flush()
    logger.info(
        "Character created",
        world_id=world_id,
        character_id=character.id,
        owner_id=owner_id,
    )
    reloaded = await _get(db, world_id, character.id)
    assert reloaded is not None
    await refresh_references(
        db, world_id, ContentKind.CHARACTER, reloaded.id, reloaded.body
    )
    return reloaded


async def list_characters(
    db: AsyncSession,
    world_id: uuid.UUID,
    user: User,
    *,
    include_drafts: bool = True,
) -> list[CharacterModel]:
    await readable_world(db, world_id, user)
    stmt = (
        select(CharacterModel)
        .options(
            selectinload(CharacterModel.owner),
            selectinload(CharacterModel.image),
        )
        .where(CharacterModel.world_id == world_id)
        .order_by(CharacterModel.name.asc())
    )
    if include_drafts:
        stmt = stmt.where(_draft_visible(user))
    else:
        stmt = stmt.where(CharacterModel.is_draft.is_(False))
    return list((await db.scalars(stmt)).all())


async def get_character(
    db: AsyncSession, world_id: uuid.UUID, character_id: uuid.UUID, user: User
) -> CharacterModel:
    await readable_world(db, world_id, user)
    character = await _get(db, world_id, character_id)
    if character is None or (character.is_draft and character.owner_id != user.id):
        raise CharacterNotFoundException(character_id)
    return character


async def update_character(
    db: AsyncSession,
    world_id: uuid.UUID,
    character_id: uuid.UUID,
    data: CharacterUpdate,
    user: User,
) -> CharacterModel:
    world = await readable_world(db, world_id, user)
    character = await _get(db, world_id, character_id)
    if character is None:
        raise CharacterNotFoundException(character_id)
    await _require_manage(db, world, character, user)
    require_content_update(character, data)
    if data.name is not None:
        character.name = data.name
    if data.title is not None:
        character.title = data.title
    if data.short_description is not None:
        character.short_description = data.short_description
    if data.body is not None:
        character.body = data.body
    if data.tint is not None:
        character.tint = data.tint
    if data.animal is not None:
        character.animal = data.animal
    if data.locked is not None:
        character.locked = data.locked
    if data.is_draft is not None:
        character.is_draft = data.is_draft
    await db.flush()
    await db.refresh(character, ["updated_at"])
    await refresh_references(
        db, world_id, ContentKind.CHARACTER, character.id, character.body
    )
    return character


async def delete_character(
    db: AsyncSession, world_id: uuid.UUID, character_id: uuid.UUID, user: User
) -> None:
    world = await readable_world(db, world_id, user)
    character = await _get(db, world_id, character_id)
    if character is None:
        raise CharacterNotFoundException(character_id)
    await _require_manage(db, world, character, user)
    await db.delete(character)
    await db.flush()


async def upload_character_image(
    db: AsyncSession,
    world_id: uuid.UUID,
    character_id: uuid.UUID,
    upload: UploadFile,
    user: User,
    filesystem: FileSystem,
) -> CharacterModel:
    world = await readable_world(db, world_id, user)
    character = await _get(db, world_id, character_id)
    if character is None:
        raise CharacterNotFoundException(character_id)
    await _require_manage(db, world, character, user)
    image = await store_image(
        db,
        filesystem,
        upload,
        location_prefix=f"worlds/{world_id}/characters/{character_id}",
        previous=character.image,
    )
    character.image = image
    await db.flush()
    await db.refresh(character, ["updated_at"])
    return character


async def read_character_image(
    db: AsyncSession,
    world_id: uuid.UUID,
    character_id: uuid.UUID,
    user: User,
    filesystem: FileSystem,
) -> tuple[FileModel, bytes]:
    character = await get_character(db, world_id, character_id, user)
    if character.image is None:
        raise ImageNotFoundError("This character does not have an image")
    return character.image, await read_image(filesystem, character.image)


async def count_characters(db: AsyncSession, world_id: uuid.UUID) -> int:
    return (
        await db.scalar(
            select(func.count())
            .select_from(CharacterModel)
            .where(CharacterModel.world_id == world_id)
        )
    ) or 0
