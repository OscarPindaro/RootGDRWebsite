import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import get_current_user
from ..dependencies import get_db_session
from ..schemas import ListResponse
from ..users.schemas import User
from .models import PageModel
from .schemas import PageCreate, PageResponse, PageSummary, PageUpdate
from .service import (
    create_page,
    delete_page,
    get_page,
    list_pages,
    update_page,
)

router = APIRouter(prefix="/api/worlds/{world_id}/pages", tags=["pages"])


def _to_response(page: PageModel) -> PageResponse:
    return PageResponse.model_validate(page)


@router.post("/", response_model=PageResponse, status_code=status.HTTP_201_CREATED)
async def create_page_route(
    world_id: uuid.UUID,
    data: PageCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> PageResponse:
    """Create a page (master only)."""
    return _to_response(await create_page(db, world_id, data, user))


@router.get("/", response_model=ListResponse[PageSummary])
async def list_pages_route(
    world_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> ListResponse[PageSummary]:
    """List the pages of an accessible world in menu order."""
    return ListResponse(
        data=[
            PageSummary.model_validate(p) for p in await list_pages(db, world_id, user)
        ]
    )


@router.get("/{page_id}", response_model=PageResponse)
async def get_page_route(
    world_id: uuid.UUID,
    page_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> PageResponse:
    """Return one page."""
    return _to_response(await get_page(db, world_id, page_id, user))


@router.patch("/{page_id}", response_model=PageResponse)
async def update_page_route(
    world_id: uuid.UUID,
    page_id: uuid.UUID,
    data: PageUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> PageResponse:
    """Update a page (master only)."""
    return _to_response(await update_page(db, world_id, page_id, data, user))


@router.delete("/{page_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_page_route(
    world_id: uuid.UUID,
    page_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> None:
    """Delete a page (master only)."""
    await delete_page(db, world_id, page_id, user)
