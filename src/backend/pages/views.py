import uuid

from fastapi import APIRouter, Depends, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from jinjax.catalog import Catalog
from sqlalchemy.ext.asyncio import AsyncSession

from ..access import master_world
from ..auth.dependencies import get_current_user
from ..content.constants import ContentKind
from ..content.policy import require_draft
from ..content.view_helpers import (
    split_published_drafts,
    tint_options,
    world_page,
    render_document,
)
from ..correlation import set_world_id
from ..dependencies import get_catalog_dep, get_db_session
from ..navigation import Crumb, MetadataField
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
        Crumb(label="Pagine", href=f"/worlds/{world.id}/pages"),
        *extra,
    ]


@router.get("/worlds/{world_id}/pages", response_class=HTMLResponse)
async def pages_page(
    world_id: uuid.UUID,
    catalog: Catalog = Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    set_world_id(str(world_id))
    world, context, nav, rail = await world_page(db, world_id, user, "pagine")
    pages = await list_pages(db, world_id, user)
    published, drafts = split_published_drafts(pages)
    return catalog.render(
        "pages.pages.PageList",
        world=world,
        world_context=context,
        nav=nav,
        pages=rail,
        rows=list(enumerate(published, start=1)),
        drafts=drafts,
        can_manage=await is_master(db, world, user),
        crumbs=_crumbs(world),
        current_user=user,
    )


@router.get("/worlds/{world_id}/pages/new")
async def page_new_page(world_id: uuid.UUID) -> RedirectResponse:
    return RedirectResponse(f"/worlds/{world_id}/pages", status_code=303)


@router.post("/worlds/{world_id}/pages/new")
async def page_new_submit(
    world_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
) -> Response:
    page = await create_page(
        db, world_id, PageCreate(title="Nuova pagina", is_draft=True), user
    )
    return _htmx_redirect(f"/worlds/{world_id}/pages/{page.slug}?edit=1")


@router.get("/worlds/{world_id}/pages/{slug}", response_class=HTMLResponse)
async def page_detail_page(
    world_id: uuid.UUID,
    slug: str,
    edit: bool = False,
    catalog: Catalog = Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    set_world_id(str(world_id))
    world, context, nav, rail = await world_page(db, world_id, user, "pagine")
    page = await get_page_by_slug(db, world_id, slug, user)
    short_html, body_html, links = await render_document(
        db, world_id, ContentKind.PAGE, page
    )
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
        metadata=[
            MetadataField(name="slug", label="Slug", kind="text", value=page.slug),
            MetadataField(
                name="menu_position",
                label="Posizione menu",
                kind="number",
                value=page.menu_position,
            ),
            MetadataField(
                name="tint",
                label="Colore",
                kind="tint",
                value=page.tint,
                options=tint_options(),
            ),
        ],
        auto_edit=edit,
        short_html=short_html,
        body_html=body_html,
        links=links,
        others=others,
        can_manage=await is_master(db, world, user),
        crumbs=_crumbs(world, Crumb(label=page.slug)),
        current_user=user,
    )


@router.get("/worlds/{world_id}/pages/{page_id}/edit")
async def page_edit_page(
    world_id: uuid.UUID,
    page_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
) -> RedirectResponse:
    page = await get_page(db, world_id, page_id, user)
    return RedirectResponse(
        f"/worlds/{world_id}/pages/{page.slug}?edit=1", status_code=303
    )


@router.post("/worlds/{world_id}/pages/{page_id}/cancel-draft")
async def page_cancel_draft(
    world_id: uuid.UUID,
    page_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
) -> Response:
    page = await get_page(db, world_id, page_id, user)
    require_draft(page)
    await delete_page(db, world_id, page_id, user)
    return _htmx_redirect(f"/worlds/{world_id}/pages")


@router.delete("/worlds/{world_id}/pages/{page_id}")
async def page_delete(
    world_id: uuid.UUID,
    page_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
) -> Response:
    await delete_page(db, world_id, page_id, user)
    return _htmx_redirect(f"/worlds/{world_id}/pages")
