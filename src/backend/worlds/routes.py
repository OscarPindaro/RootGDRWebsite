import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import get_current_user
from ..dependencies import get_db_session
from ..schemas import PagedResponse
from ..users.schemas import User
from .models import WorldModel
from .schemas import WorldCreate, WorldResponse, WorldUpdate
from .service import create_world, delete_world, get_world, get_worlds, update_world

router = APIRouter(prefix="/api/worlds", tags=["worlds"])


def _to_response(world: WorldModel) -> WorldResponse:
    return WorldResponse.model_validate(world)


@router.post("/", response_model=WorldResponse, status_code=status.HTTP_201_CREATED)
async def create_world_route(
    data: WorldCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WorldResponse:
    """Create a private world owned by the current user."""
    return _to_response(await create_world(db, data, user))


@router.get("/", response_model=PagedResponse[WorldResponse])
async def list_worlds(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    include_shared_with: bool = Query(False),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> PagedResponse[WorldResponse]:
    """List the worlds accessible to the current user."""
    worlds, total = await get_worlds(db, user, page, page_size, include_shared_with)
    return PagedResponse(
        data=[_to_response(world) for world in worlds],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{world_id}", response_model=WorldResponse)
async def get_world_route(
    world_id: uuid.UUID,
    include_shared_with: bool = Query(False),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WorldResponse:
    """Return one accessible world."""
    return _to_response(await get_world(db, world_id, user, include_shared_with))


@router.patch("/{world_id}", response_model=WorldResponse)
async def update_world_route(
    world_id: uuid.UUID,
    data: WorldUpdate,
    include_shared_with: bool = Query(False),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WorldResponse:
    """Update a world when the current user owns it or is an administrator."""
    return _to_response(
        await update_world(db, world_id, data, user, include_shared_with)
    )


@router.delete("/{world_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_world_route(
    world_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a world when the current user owns it or is an administrator."""
    await delete_world(db, world_id, user)
