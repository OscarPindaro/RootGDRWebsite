import uuid

from fastapi import APIRouter, Depends, Response
from fastapi.responses import HTMLResponse
from jinjax.catalog import Catalog
from sqlalchemy.ext.asyncio import AsyncSession

from ..access import master_world
from ..auth.dependencies import get_current_user
from ..content.view_helpers import tint_options, world_page
from ..correlation import set_world_id
from ..dependencies import get_catalog_dep, get_db_session
from ..navigation import Crumb
from ..users.schemas import User
from ..worlds.service import is_master
from ..worlds.views import _htmx_redirect
from .exceptions import PageSlugConflictException
from .schemas import PageCreate, PageUpdate, slugify
from .service import (
    create_page,
    delete_page,
    get_page,
    get_page_by_slug,
    list_pages,
    update_page,
)

router = APIRouter(tags=["page-views"])


def _crumbs(world, *extra: Crumb) -> list[Crumb]:
    return [
        Crumb(label="Mondi", href="/worlds"),
        Crumb(label=world.name, href=f"/worlds/{world.id}"),
        Crumb(label="Pagine", href=f"/worlds/{world.id}/pagine"),
        *extra,
    ]


@router.get("/worlds/{world_id}/pagine", response_class=HTMLResponse)
async def pages_page(
    world_id: uuid.UUID,
    catalog: Catalog = Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    set_world_id(str(world_id))
    world, context, nav, rail = await world_page(db, world_id, user, "pagine")
    pages = await list_pages(db, world_id, user)
    return catalog.render(
        "pages.pages.PageList",
        world=world,
        world_context=context,
        nav=nav,
        pages=rail,
        rows=list(enumerate(pages, start=1)),
        can_manage=await is_master(db, world, user),
        crumbs=_crumbs(world),
        current_user=user,
    )


@router.get("/worlds/{world_id}/pagine/new", response_class=HTMLResponse)
async def page_new_page(
    world_id: uuid.UUID,
    catalog: Catalog = Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    set_world_id(str(world_id))
    world, context, nav, rail = await world_page(db, world_id, user, "pagine")
    await master_world(db, world_id, user)
    return catalog.render(
        "pages.pages.PageForm",
        world=world,
        world_context=context,
        nav=nav,
        pages=rail,
        page=None,
        tints=tint_options(),
        crumbs=_crumbs(world, Crumb(label="Nuova")),
        current_user=user,
    )


@router.post("/worlds/{world_id}/pagine/new")
async def page_new_submit(
    world_id: uuid.UUID,
    data: PageCreate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> Response:
    page = await create_page(db, world_id, data, user)
    return _htmx_redirect(f"/worlds/{world_id}/pagine/{page.slug}")


@router.get("/worlds/{world_id}/pagine/{slug}", response_class=HTMLResponse)
async def page_detail_page(
    world_id: uuid.UUID,
    slug: str,
    catalog: Catalog = Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    set_world_id(str(world_id))
    world, context, nav, rail = await world_page(db, world_id, user, "pagine")
    page = await get_page_by_slug(db, world_id, slug, user)
    others = [
        other for other in await list_pages(db, world_id, user) if other.id != page.id
    ]
    return catalog.render(
        "pages.pages.PageDetail",
        world=world,
        world_context=context,
        nav=nav,
        pages=rail,
        page=page,
        others=others,
        can_manage=await is_master(db, world, user),
        crumbs=_crumbs(world, Crumb(label=page.slug)),
        current_user=user,
    )


@router.get("/worlds/{world_id}/pagine/{page_id}/edit", response_class=HTMLResponse)
async def page_edit_page(
    world_id: uuid.UUID,
    page_id: uuid.UUID,
    catalog: Catalog = Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    set_world_id(str(world_id))
    world, context, nav, rail = await world_page(db, world_id, user, "pagine")
    page = await get_page(db, world_id, page_id, user)
    return catalog.render(
        "pages.pages.PageForm",
        world=world,
        world_context=context,
        nav=nav,
        pages=rail,
        page=page,
        tints=tint_options(),
        crumbs=_crumbs(
            world,
            Crumb(label=page.slug, href=f"/worlds/{world_id}/pagine/{page.slug}"),
            Crumb(label="Modifica"),
        ),
        current_user=user,
    )


@router.post("/worlds/{world_id}/pagine/{page_id}")
async def page_edit_submit(
    world_id: uuid.UUID,
    page_id: uuid.UUID,
    data: PageUpdate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> Response:
    page = await update_page(db, world_id, page_id, data, user)
    return _htmx_redirect(f"/worlds/{world_id}/pagine/{page.slug}")


@router.delete("/worlds/{world_id}/pagine/{page_id}")
async def page_delete(
    world_id: uuid.UUID,
    page_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> Response:
    await delete_page(db, world_id, page_id, user)
    return _htmx_redirect(f"/worlds/{world_id}/pagine")
