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
from .models import NpcModel
from .schemas import NpcCreate, NpcResponse, NpcSummary, NpcUpdate
from .service import (
    create_npc,
    delete_npc,
    get_npc,
    list_npcs,
    read_npc_image,
    update_npc,
    upload_npc_image,
)

router = APIRouter(prefix="/api/worlds/{world_id}/npcs", tags=["npcs"])


def _to_response(npc: NpcModel) -> NpcResponse:
    return NpcResponse.model_validate(npc)


@router.post("/", response_model=NpcResponse, status_code=status.HTTP_201_CREATED)
async def create_npc_route(
    world_id: uuid.UUID,
    data: NpcCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> NpcResponse:
    """Create an NPC (master only)."""
    return _to_response(await create_npc(db, world_id, data, user))


@router.get("/", response_model=ListResponse[NpcSummary])
async def list_npcs_route(
    world_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> ListResponse[NpcSummary]:
    """List the NPCs of an accessible world."""
    return ListResponse(
        data=[NpcSummary.model_validate(n) for n in await list_npcs(db, world_id, user)]
    )


@router.put("/{npc_id}/image", response_model=NpcResponse)
async def upload_npc_image_route(
    world_id: uuid.UUID,
    npc_id: uuid.UUID,
    image: UploadFile = File(...),
    user: User = Depends(get_current_user),
    filesystem: FileSystem = Depends(get_filesystem),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> NpcResponse:
    """Replace an NPC image (master only)."""
    return _to_response(
        await upload_npc_image(db, world_id, npc_id, image, user, filesystem)
    )


@router.get("/{npc_id}/image", response_class=Response)
async def get_npc_image_route(
    world_id: uuid.UUID,
    npc_id: uuid.UUID,
    user: User = Depends(get_current_user),
    filesystem: FileSystem = Depends(get_filesystem),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> Response:
    """Return an NPC image for a readable world."""
    image, content = await read_npc_image(db, world_id, npc_id, user, filesystem)
    media_type = mimetypes.guess_type(image.name)[0] or "application/octet-stream"
    return Response(
        content,
        media_type=media_type,
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(image.name, safe='')}",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/{npc_id}", response_model=NpcResponse)
async def get_npc_route(
    world_id: uuid.UUID,
    npc_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> NpcResponse:
    """Return one NPC."""
    return _to_response(await get_npc(db, world_id, npc_id, user))


@router.patch("/{npc_id}", response_model=NpcResponse)
async def update_npc_route(
    world_id: uuid.UUID,
    npc_id: uuid.UUID,
    data: NpcUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> NpcResponse:
    """Update an NPC (master only)."""
    return _to_response(await update_npc(db, world_id, npc_id, data, user))


@router.delete("/{npc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_npc_route(
    world_id: uuid.UUID,
    npc_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> None:
    """Delete an NPC (master only)."""
    await delete_npc(db, world_id, npc_id, user)
