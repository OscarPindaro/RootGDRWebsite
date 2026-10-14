import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import get_current_user
from ..dependencies import get_db_session
from ..schemas import PagedResponse
from ..users.schemas import User
from .schemas import (
    AssetCreate,
    AssetResponse,
    AssetSummary,
    AssetUpdate,
    LibraryCreate,
    LibraryResponse,
    SectionCreate,
    SectionResponse,
)
from .service import (
    asset_response,
    create_asset,
    create_library,
    create_section,
    delete_asset,
    get_asset,
    list_assets,
    list_libraries,
    update_asset,
)

router = APIRouter(prefix="/api/libraries", tags=["libraries"])


@router.get("", response_model=list[LibraryResponse])
async def list_libraries_route(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> list[LibraryResponse]:
    """Every library the caller may read: all of them for an admin, the mastered
    worlds' ones for a world master, and none otherwise."""
    return await list_libraries(db, user)


@router.post("", response_model=LibraryResponse, status_code=status.HTTP_201_CREATED)
async def create_library_route(
    data: LibraryCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> LibraryResponse:
    library = await create_library(db, data, user)
    return LibraryResponse(
        id=library.id,
        name=library.name,
        scope=library.scope,
        world_id=library.world_id,
        version=library.version,
        created_at=library.created_at,
        updated_at=library.updated_at,
    )


@router.post(
    "/{library_id}/sections",
    response_model=SectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_section_route(
    library_id: uuid.UUID,
    data: SectionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> SectionResponse:
    section = await create_section(db, library_id, data, user)
    return SectionResponse(
        id=section.id,
        name=section.name,
        position=section.position,
        created_at=section.created_at,
        updated_at=section.updated_at,
    )


@router.get("/{library_id}/assets", response_model=PagedResponse[AssetSummary])
async def list_assets_route(
    library_id: uuid.UUID,
    section_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> PagedResponse[AssetSummary]:
    data, total = await list_assets(db, library_id, user, section_id, page, page_size)
    return PagedResponse(data=data, total=total, page=page, page_size=page_size)


@router.post(
    "/{library_id}/assets",
    response_model=AssetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_asset_route(
    library_id: uuid.UUID,
    data: AssetCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> AssetResponse:
    return await asset_response(db, await create_asset(db, library_id, data, user))


@router.get("/{library_id}/assets/{asset_id}", response_model=AssetResponse)
async def get_asset_route(
    library_id: uuid.UUID,
    asset_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> AssetResponse:
    return await asset_response(db, await get_asset(db, library_id, asset_id, user))


@router.patch("/{library_id}/assets/{asset_id}", response_model=AssetResponse)
async def update_asset_route(
    library_id: uuid.UUID,
    asset_id: uuid.UUID,
    data: AssetUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> AssetResponse:
    return await asset_response(
        db, await update_asset(db, library_id, asset_id, data, user)
    )


@router.delete(
    "/{library_id}/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_asset_route(
    library_id: uuid.UUID,
    asset_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> None:
    await delete_asset(db, library_id, asset_id, user)
