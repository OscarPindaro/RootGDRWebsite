import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from jinjax.catalog import Catalog
from sqlalchemy.ext.asyncio import AsyncSession

from ..access import readable_world
from ..auth.dependencies import get_current_user
from ..correlation import set_world_id
from ..db.enums import WorldRole
from ..dependencies import get_catalog_dep, get_db_session
from ..navigation import Crumb, WorldContext, build_quicks, world_nav
from ..users.schemas import User
from .models import WorldModel
from .overview import build_overview
from .schemas import WorldSummary
from .service import get_worlds, role_for_world

router = APIRouter(tags=["world-views"])


def _world_context(world: WorldModel, role: WorldRole) -> WorldContext:
    label = "Master" if role == WorldRole.MASTER else "Giocatore"
    return WorldContext(id=str(world.id), name=world.name, role=label)


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


@router.get("/worlds/{world_id}", response_class=HTMLResponse)
async def world_overview_page(
    world_id: uuid.UUID,
    catalog: Catalog = Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Render the overview of one world."""
    set_world_id(str(world_id))
    world = await readable_world(db, world_id, user, include_members=True)
    role = role_for_world(world, user)
    overview = await build_overview(db, world)
    return catalog.render(
        "pages.worlds.WorldOverview",
        world=world,
        world_context=_world_context(world, role),
        nav=world_nav(str(world.id), "mondo", overview.counts),
        quicks=build_quicks(str(world.id), overview.counts),
        overview=overview,
        crumbs=[Crumb(label="Mondi", href="/worlds"), Crumb(label=world.name)],
        current_user=user,
    )
