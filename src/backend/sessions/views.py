import uuid

from fastapi import APIRouter, Depends, Response
from fastapi.responses import HTMLResponse
from jinjax.catalog import Catalog
from sqlalchemy.ext.asyncio import AsyncSession

from ..access import master_world
from ..auth.dependencies import get_current_user
from ..content.view_helpers import split_published_drafts, tint_options, world_page
from ..correlation import set_world_id
from ..dependencies import get_catalog_dep, get_db_session
from ..navigation import Crumb
from ..users.schemas import User
from ..worlds.service import is_master
from ..worlds.views import _htmx_redirect
from .schemas import SessionCreate, SessionUpdate
from .service import (
    create_session,
    delete_session,
    get_neighbours,
    get_session,
    list_sessions,
    update_session,
)

router = APIRouter(tags=["session-views"])


def _crumbs(world, *extra: Crumb) -> list[Crumb]:
    return [
        Crumb(label="Mondi", href="/worlds"),
        Crumb(label=world.name, href=f"/worlds/{world.id}"),
        Crumb(label="Sessioni", href=f"/worlds/{world.id}/sessioni"),
        *extra,
    ]


@router.get("/worlds/{world_id}/sessioni", response_class=HTMLResponse)
async def sessions_page(
    world_id: uuid.UUID,
    catalog: Catalog = Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Render the session ledger, newest first."""
    set_world_id(str(world_id))
    world, context, nav, rail_pages = await world_page(db, world_id, user, "sessioni")
    sessions = await list_sessions(db, world_id, user)
    published, drafts = split_published_drafts(sessions, user)
    numbered = list(enumerate(published, start=1))
    return catalog.render(
        "pages.sessions.SessionList",
        world=world,
        world_context=context,
        nav=nav,
        pages=rail_pages,
        rows=list(reversed(numbered)),
        drafts=drafts,
        can_manage=await is_master(db, world, user),
        crumbs=_crumbs(world),
        current_user=user,
    )


@router.get("/worlds/{world_id}/sessioni/new", response_class=HTMLResponse)
async def session_new_page(
    world_id: uuid.UUID,
    catalog: Catalog = Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Render the create-session form (master only)."""
    set_world_id(str(world_id))
    world, context, nav, rail_pages = await world_page(db, world_id, user, "sessioni")
    await master_world(db, world_id, user)
    return catalog.render(
        "pages.sessions.SessionForm",
        world=world,
        world_context=context,
        nav=nav,
        pages=rail_pages,
        session=None,
        tints=tint_options(),
        crumbs=_crumbs(world, Crumb(label="Nuova")),
        current_user=user,
    )


@router.post("/worlds/{world_id}/sessioni/new")
async def session_new_submit(
    world_id: uuid.UUID,
    data: SessionCreate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> Response:
    session = await create_session(db, world_id, data, user)
    return _htmx_redirect(f"/worlds/{world_id}/sessioni/{session.id}")


@router.get("/worlds/{world_id}/sessioni/{session_id}", response_class=HTMLResponse)
async def session_detail_page(
    world_id: uuid.UUID,
    session_id: uuid.UUID,
    catalog: Catalog = Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    set_world_id(str(world_id))
    world, context, nav, rail_pages = await world_page(db, world_id, user, "sessioni")
    session = await get_session(db, world_id, session_id, user)
    previous, following = await get_neighbours(db, world_id, session_id, user)
    return catalog.render(
        "pages.sessions.SessionDetail",
        world=world,
        world_context=context,
        nav=nav,
        pages=rail_pages,
        session=session,
        previous=previous,
        following=following,
        can_manage=await is_master(db, world, user),
        crumbs=_crumbs(world, Crumb(label=session.title)),
        current_user=user,
    )


@router.get(
    "/worlds/{world_id}/sessioni/{session_id}/edit", response_class=HTMLResponse
)
async def session_edit_page(
    world_id: uuid.UUID,
    session_id: uuid.UUID,
    catalog: Catalog = Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    set_world_id(str(world_id))
    world, context, nav, rail_pages = await world_page(db, world_id, user, "sessioni")
    session = await get_session(db, world_id, session_id, user)
    return catalog.render(
        "pages.sessions.SessionForm",
        world=world,
        world_context=context,
        nav=nav,
        pages=rail_pages,
        session=session,
        tints=tint_options(),
        crumbs=_crumbs(
            world,
            Crumb(
                label=session.title, href=f"/worlds/{world_id}/sessioni/{session_id}"
            ),
            Crumb(label="Modifica"),
        ),
        current_user=user,
    )


@router.post("/worlds/{world_id}/sessioni/{session_id}")
async def session_edit_submit(
    world_id: uuid.UUID,
    session_id: uuid.UUID,
    data: SessionUpdate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> Response:
    await update_session(db, world_id, session_id, data, user)
    return _htmx_redirect(f"/worlds/{world_id}/sessioni/{session_id}")


@router.delete("/worlds/{world_id}/sessioni/{session_id}")
async def session_delete(
    world_id: uuid.UUID,
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
) -> Response:
    await delete_session(db, world_id, session_id, user)
    return _htmx_redirect(f"/worlds/{world_id}/sessioni")
