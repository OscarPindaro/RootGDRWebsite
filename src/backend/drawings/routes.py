import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import get_current_admin_user
from ..dependencies import get_db_session
from ..schemas import ListResponse
from ..users.schemas import User
from .models import DrawingModel
from .schemas import (
    DrawingCreate,
    DrawingResponse,
    DrawingSummary,
    DrawingUpdate,
    SceneDocument,
)
from .service import (
    create_drawing,
    delete_drawing,
    get_drawing,
    list_drawings,
    node_count_of,
    scene_of,
    update_drawing,
    validate_scene,
)

router = APIRouter(prefix="/api/drawings", tags=["drawings"])


def _response(model: DrawingModel) -> DrawingResponse:
    return DrawingResponse(
        id=model.id,
        title=model.title,
        node_count=node_count_of(model),
        version=model.version,
        created_at=model.created_at,
        updated_at=model.updated_at,
        scene=scene_of(model),
    )


@router.post("/", response_model=DrawingResponse, status_code=status.HTTP_201_CREATED)
async def create_drawing_route(
    data: DrawingCreate,
    user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> DrawingResponse:
    """Create a drawing (admin only)."""
    return _response(await create_drawing(db, data, user))


@router.get("/", response_model=ListResponse[DrawingSummary])
async def list_drawings_route(
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> ListResponse[DrawingSummary]:
    """List every drawing (admin only)."""
    return ListResponse(data=await list_drawings(db, user, page, page_size))


@router.post("/validate", response_model=SceneDocument)
async def validate_scene_route(
    data: SceneDocument, user: User = Depends(get_current_admin_user)
) -> SceneDocument:
    return validate_scene(data, user)


@router.get("/{drawing_id}", response_model=DrawingResponse)
async def get_drawing_route(
    drawing_id: uuid.UUID,
    user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> DrawingResponse:
    """Return one drawing with its editable scene (admin only)."""
    return _response(await get_drawing(db, drawing_id, user))


@router.patch("/{drawing_id}", response_model=DrawingResponse)
async def update_drawing_route(
    drawing_id: uuid.UUID,
    data: DrawingUpdate,
    user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> DrawingResponse:
    """Save a drawing (admin only). A stale version is a 409."""
    return _response(await update_drawing(db, drawing_id, data, user))


@router.delete("/{drawing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_drawing_route(
    drawing_id: uuid.UUID,
    user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> None:
    """Delete a drawing (admin only)."""
    await delete_drawing(db, drawing_id, user)
