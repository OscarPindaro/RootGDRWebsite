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
from .models import PlaceModel
from .schemas import PlaceCreate, PlaceResponse, PlaceSummary, PlaceUpdate
from .service import (
    create_place,
    delete_place,
    get_place,
    list_places,
    read_place_image,
    update_place,
    upload_place_image,
)

router = APIRouter(prefix="/api/worlds/{world_id}/places", tags=["places"])


def _to_response(place: PlaceModel) -> PlaceResponse:
    return PlaceResponse.model_validate(place)


@router.post("/", response_model=PlaceResponse, status_code=status.HTTP_201_CREATED)
async def create_place_route(
    world_id: uuid.UUID,
    data: PlaceCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> PlaceResponse:
    """Create an Luogo (master only)."""
    return _to_response(await create_place(db, world_id, data, user))


@router.get("/", response_model=ListResponse[PlaceSummary])
async def list_places_route(
    world_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> ListResponse[PlaceSummary]:
    """List the Luogos of an accessible world."""
    return ListResponse(
        data=[
            PlaceSummary.model_validate(n)
            for n in await list_places(db, world_id, user)
        ]
    )


@router.put("/{place_id}/image", response_model=PlaceResponse)
async def upload_place_image_route(
    world_id: uuid.UUID,
    place_id: uuid.UUID,
    image: UploadFile = File(...),
    user: User = Depends(get_current_user),
    filesystem: FileSystem = Depends(get_filesystem),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> PlaceResponse:
    """Replace an Luogo image (master only)."""
    return _to_response(
        await upload_place_image(db, world_id, place_id, image, user, filesystem)
    )


@router.get("/{place_id}/image", response_class=Response)
async def get_place_image_route(
    world_id: uuid.UUID,
    place_id: uuid.UUID,
    user: User = Depends(get_current_user),
    filesystem: FileSystem = Depends(get_filesystem),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> Response:
    """Return an Luogo image for a readable world."""
    image, content = await read_place_image(db, world_id, place_id, user, filesystem)
    media_type = mimetypes.guess_type(image.name)[0] or "application/octet-stream"
    return Response(
        content,
        media_type=media_type,
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(image.name, safe='')}",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/{place_id}", response_model=PlaceResponse)
async def get_place_route(
    world_id: uuid.UUID,
    place_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> PlaceResponse:
    """Return one Luogo."""
    return _to_response(await get_place(db, world_id, place_id, user))


@router.patch("/{place_id}", response_model=PlaceResponse)
async def update_place_route(
    world_id: uuid.UUID,
    place_id: uuid.UUID,
    data: PlaceUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> PlaceResponse:
    """Update an Luogo (master only)."""
    return _to_response(await update_place(db, world_id, place_id, data, user))


@router.delete("/{place_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_place_route(
    world_id: uuid.UUID,
    place_id: uuid.UUID,
    user: User = Depends(get_current_user),
    filesystem: FileSystem = Depends(get_filesystem),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> None:
    """Delete an Luogo (master only)."""
    await delete_place(db, world_id, place_id, user, filesystem)
