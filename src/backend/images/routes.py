import mimetypes
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..access import master_world, readable_world
from ..auth.dependencies import get_current_user
from ..characters.exceptions import CharacterAccessDeniedException
from ..characters.service import get_character
from ..db.enums import UserRole
from ..dependencies import get_db_session
from ..filesystem.base import FileSystem
from ..filesystem.dependencies import get_filesystem
from ..npcs.service import get_npc
from ..places.service import get_place
from ..schemas import ListResponse
from ..users.schemas import User
from ..worlds.exceptions import WorldAccessDeniedException
from ..worlds.service import get_world, is_master
from .models import ImageOwnerKind, ImageRevisionModel
from .schemas import ImageOwner, ImageRevisionResponse
from .service import (
    clear_current,
    current_file_id,
    delete_revision,
    get_revision,
    list_revisions,
    read_image,
    restore_revision,
)

router = APIRouter(
    prefix="/api/worlds/{world_id}/images/{owner_kind}/{owner_id}/revisions",
    tags=["image history"],
)


def _reference(
    world_id: uuid.UUID, owner_kind: ImageOwnerKind, owner_id: uuid.UUID
) -> ImageOwner:
    return ImageOwner(world_id=world_id, kind=owner_kind, owner_id=owner_id)


async def _authorize_read(db: AsyncSession, reference: ImageOwner, user: User) -> None:
    if reference.kind == ImageOwnerKind.WORLD:
        await get_world(db, reference.world_id, user)
    elif reference.kind == ImageOwnerKind.CHARACTER:
        await get_character(db, reference.world_id, reference.owner_id, user)
    elif reference.kind == ImageOwnerKind.NPC:
        await get_npc(db, reference.world_id, reference.owner_id, user)
    else:
        await get_place(db, reference.world_id, reference.owner_id, user)


async def _authorize_manage(
    db: AsyncSession, reference: ImageOwner, user: User
) -> None:
    if reference.kind == ImageOwnerKind.WORLD:
        world = await get_world(db, reference.world_id, user)
        if user.role != UserRole.ADMIN and world.created_by_id != user.id:
            raise WorldAccessDeniedException(world.id)
    elif reference.kind == ImageOwnerKind.CHARACTER:
        world = await readable_world(db, reference.world_id, user)
        character = await get_character(
            db, reference.world_id, reference.owner_id, user
        )
        if character.owner_id != user.id and not await is_master(db, world, user):
            raise CharacterAccessDeniedException()
    elif reference.kind == ImageOwnerKind.NPC:
        await master_world(db, reference.world_id, user)
        await get_npc(db, reference.world_id, reference.owner_id, user)
    else:
        await master_world(db, reference.world_id, user)
        await get_place(db, reference.world_id, reference.owner_id, user)


def _response(
    revision: ImageRevisionModel, current_id: uuid.UUID | None
) -> ImageRevisionResponse:
    return ImageRevisionResponse.from_revision(revision, current_id)


@router.get("/", response_model=ListResponse[ImageRevisionResponse])
async def list_image_revisions_route(
    world_id: uuid.UUID,
    owner_kind: ImageOwnerKind,
    owner_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> ListResponse[ImageRevisionResponse]:
    reference = _reference(world_id, owner_kind, owner_id)
    await _authorize_read(db, reference, user)
    owner, revisions = await list_revisions(db, reference)
    current_id = current_file_id(owner)
    return ListResponse(data=[_response(item, current_id) for item in revisions])


@router.get("/{revision_id}/content", response_class=Response)
async def read_image_revision_route(
    world_id: uuid.UUID,
    owner_kind: ImageOwnerKind,
    owner_id: uuid.UUID,
    revision_id: uuid.UUID,
    user: User = Depends(get_current_user),
    filesystem: FileSystem = Depends(get_filesystem),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> Response:
    reference = _reference(world_id, owner_kind, owner_id)
    await _authorize_read(db, reference, user)
    _, revision = await get_revision(db, reference, revision_id)
    media_type = (
        mimetypes.guess_type(revision.file.name)[0] or "application/octet-stream"
    )
    return Response(
        await read_image(filesystem, revision.file),
        media_type=media_type,
        headers={
            "Content-Disposition": (
                f"inline; filename*=UTF-8''{quote(revision.file.name, safe='')}"
            ),
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/{revision_id}/restore", response_model=ImageRevisionResponse)
async def restore_image_revision_route(
    world_id: uuid.UUID,
    owner_kind: ImageOwnerKind,
    owner_id: uuid.UUID,
    revision_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> ImageRevisionResponse:
    reference = _reference(world_id, owner_kind, owner_id)
    await _authorize_manage(db, reference, user)
    revision = await restore_revision(db, reference, revision_id)
    return _response(revision, revision.file_id)


@router.delete("/current", status_code=status.HTTP_204_NO_CONTENT)
async def clear_current_image_route(
    world_id: uuid.UUID,
    owner_kind: ImageOwnerKind,
    owner_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> None:
    reference = _reference(world_id, owner_kind, owner_id)
    await _authorize_manage(db, reference, user)
    await clear_current(db, reference)


@router.delete("/{revision_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_image_revision_route(
    world_id: uuid.UUID,
    owner_kind: ImageOwnerKind,
    owner_id: uuid.UUID,
    revision_id: uuid.UUID,
    replacement_id: uuid.UUID | None = Query(None),
    clear: bool = Query(False),
    user: User = Depends(get_current_user),
    filesystem: FileSystem = Depends(get_filesystem),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> None:
    reference = _reference(world_id, owner_kind, owner_id)
    await _authorize_manage(db, reference, user)
    await delete_revision(
        db,
        filesystem,
        reference,
        revision_id,
        replacement_id=replacement_id,
        clear=clear,
    )
