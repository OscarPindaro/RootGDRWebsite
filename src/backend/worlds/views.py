from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from jinjax.catalog import Catalog
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import get_current_user
from ..dependencies import get_catalog_dep, get_db_session
from ..users.schemas import User
from .schemas import WorldSummary
from .service import get_worlds, role_for_world

router = APIRouter(tags=["world-views"])


@router.get("/worlds", response_class=HTMLResponse)
async def worlds_page(
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=60),
    catalog: Catalog = Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Render a paginated grid of worlds accessible to the current user."""
    worlds, total = await get_worlds(db, user, page, page_size, include_members=True)
    summaries = [
        WorldSummary(
            id=world.id,
            name=world.name,
            description=world.description,
            image_url=world.image_url,
            role=role_for_world(world, user),
            volume=(page - 1) * page_size + index + 1,
            updated_at=world.updated_at,
        )
        for index, world in enumerate(worlds)
    ]
    return catalog.render(
        "pages.worlds.WorldList",
        worlds=summaries,
        total=total,
        page=page,
        page_size=page_size,
        current_user=user,
    )
