import mimetypes
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import get_current_user
from ..dependencies import get_db_session
from ..filesystem.base import FileSystem
from ..filesystem.dependencies import get_filesystem
from ..schemas import ListResponse
from ..users.schemas import User
from .models import CharacterModel
from .schemas import (
    CharacterCreate,
    CharacterResponse,
    CharacterSummary,
    CharacterUpdate,
)
from .service import (
    create_character,
    delete_character,
    get_character,
    list_characters,
    read_character_image,
    update_character,
    upload_character_image,
)

router = APIRouter(prefix="/api/worlds/{world_id}/characters", tags=["characters"])


def _to_response(character: CharacterModel) -> CharacterResponse:
    return CharacterResponse.model_validate(character)


@router.post("/", response_model=CharacterResponse, status_code=status.HTTP_201_CREATED)
async def create_character_route(
    world_id: uuid.UUID,
    data: CharacterCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> CharacterResponse:
    """Create a character in an accessible world."""
    return _to_response(await create_character(db, world_id, data, user))


@router.get("/", response_model=ListResponse[CharacterSummary])
async def list_characters_route(
    world_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> ListResponse[CharacterSummary]:
    """List the characters of an accessible world."""
    characters = await list_characters(db, world_id, user)
    return ListResponse(data=[CharacterSummary.model_validate(c) for c in characters])


@router.put("/{character_id}/image", response_model=CharacterResponse)
async def upload_character_image_route(
    world_id: uuid.UUID,
    character_id: uuid.UUID,
    image: UploadFile = File(...),
    user: User = Depends(get_current_user),
    filesystem: FileSystem = Depends(get_filesystem),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> CharacterResponse:
    """Replace a character image (owner or master)."""
    character = await upload_character_image(
        db, world_id, character_id, image, user, filesystem
    )
    return _to_response(character)


@router.get("/{character_id}/image", response_class=Response)
async def get_character_image_route(
    world_id: uuid.UUID,
    character_id: uuid.UUID,
    user: User = Depends(get_current_user),
    filesystem: FileSystem = Depends(get_filesystem),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> Response:
    """Return a character image for a readable world."""
    image, content = await read_character_image(
        db, world_id, character_id, user, filesystem
    )
    media_type = mimetypes.guess_type(image.name)[0] or "application/octet-stream"
    return Response(
        content,
        media_type=media_type,
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(image.name, safe='')}",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/{character_id}", response_model=CharacterResponse)
async def get_character_route(
    world_id: uuid.UUID,
    character_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> CharacterResponse:
    """Return one character."""
    return _to_response(await get_character(db, world_id, character_id, user))


@router.patch("/{character_id}", response_model=CharacterResponse)
async def update_character_route(
    world_id: uuid.UUID,
    character_id: uuid.UUID,
    data: CharacterUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> CharacterResponse:
    """Update a character (owner or master)."""
    return _to_response(await update_character(db, world_id, character_id, data, user))


@router.delete("/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_character_route(
    world_id: uuid.UUID,
    character_id: uuid.UUID,
    user: User = Depends(get_current_user),
    filesystem: FileSystem = Depends(get_filesystem),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> None:
    """Delete a character (owner or master)."""
    await delete_character(db, world_id, character_id, user, filesystem)
