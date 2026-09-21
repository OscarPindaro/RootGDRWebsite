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
        Crumb(label="Sessioni", href=f"/worlds/{world.id}/sessions"),
        *extra,
    ]


@router.get("/worlds/{world_id}/sessions", response_class=HTMLResponse)
async def sessions_page(
    world_id: uuid.UUID,
    catalog: Catalog = Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Render the session ledger, newest first."""
    set_world_id(str(world_id))
    world, context, nav, rail_pages = await world_page(db, world_id, user, "sessioni")
    sessions = await list_sessions(db, world_id, user)
    published, drafts = split_published_drafts(sessions)
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


@router.get("/worlds/{world_id}/sessions/new")
async def session_new_page(world_id: uuid.UUID) -> RedirectResponse:
    return RedirectResponse(f"/worlds/{world_id}/sessions", status_code=303)


@router.post("/worlds/{world_id}/sessions/new")
async def session_new_submit(
    world_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
) -> Response:
    session = await create_session(
        db,
        world_id,
        SessionCreate(
            title="Nuova sessione", in_world_date="Data da definire", is_draft=True
        ),
        user,
    )
    return _htmx_redirect(f"/worlds/{world_id}/sessions/{session.id}?edit=1")


@router.get("/worlds/{world_id}/sessions/{session_id}", response_class=HTMLResponse)
async def session_detail_page(
    world_id: uuid.UUID,
    session_id: uuid.UUID,
    edit: bool = False,
    catalog: Catalog = Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    set_world_id(str(world_id))
    world, context, nav, rail_pages = await world_page(db, world_id, user, "sessioni")
    session = await get_session(db, world_id, session_id, user)
    short_html, body_html, links = await render_document(
        db, world_id, ContentKind.SESSION, session
    )
    previous, following = await get_neighbours(db, world_id, session_id, user)
    return catalog.render(
        "pages.sessions.SessionDetail",
        world=world,
        world_context=context,
        nav=nav,
        pages=rail_pages,
        session=session,
        metadata=[
            MetadataField(
                name="in_world_date",
                label="Data nel mondo",
                kind="text",
                value=session.in_world_date,
            ),
            MetadataField(
                name="real_date",
                label="Data reale",
                kind="date",
                value=session.real_date.isoformat() if session.real_date else None,
            ),
            MetadataField(
                name="tint",
                label="Colore",
                kind="select",
                value=session.tint,
                options=tint_options(),
            ),
        ],
        auto_edit=edit,
        short_html=short_html,
        body_html=body_html,
        links=links,
        previous=previous,
        following=following,
        can_manage=await is_master(db, world, user),
        crumbs=_crumbs(world, Crumb(label=session.title)),
        current_user=user,
    )


@router.get("/worlds/{world_id}/sessions/{session_id}/edit")
async def session_edit_page(
    world_id: uuid.UUID, session_id: uuid.UUID
) -> RedirectResponse:
    return RedirectResponse(
        f"/worlds/{world_id}/sessions/{session_id}?edit=1", status_code=303
    )


@router.post("/worlds/{world_id}/sessions/{session_id}/cancel-draft")
async def session_cancel_draft(
    world_id: uuid.UUID,
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
) -> Response:
    session = await get_session(db, world_id, session_id, user)
    require_draft(session)
    await delete_session(db, world_id, session_id, user)
    return _htmx_redirect(f"/worlds/{world_id}/sessions")


@router.delete("/worlds/{world_id}/sessions/{session_id}")
async def session_delete(
    world_id: uuid.UUID,
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
) -> Response:
    await delete_session(db, world_id, session_id, user)
    return _htmx_redirect(f"/worlds/{world_id}/sessions")
