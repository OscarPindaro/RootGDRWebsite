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
from ..navigation import Crumb, MetadataField, Option
from ..sessions.service import list_sessions
from ..users.schemas import User
from ..worlds.service import is_master
from ..worlds.views import _htmx_redirect
from .models import StoryStatus
from .schemas import StoryCreate, StoryUpdate
from .service import (
    create_story,
    delete_story,
    get_story,
    list_stories,
    update_story,
)

router = APIRouter(tags=["story-views"])

_STATUS_OPTIONS = [
    Option(value=StoryStatus.OPEN.value, label="In corso"),
    Option(value=StoryStatus.CLOSED.value, label="Chiusa"),
]


def _crumbs(world, *extra: Crumb) -> list[Crumb]:
    return [
        Crumb(label="Mondi", href="/worlds"),
        Crumb(label=world.name, href=f"/worlds/{world.id}"),
        Crumb(label="Storie", href=f"/worlds/{world.id}/stories"),
        *extra,
    ]


@router.get("/worlds/{world_id}/stories", response_class=HTMLResponse)
async def stories_page(
    world_id: uuid.UUID,
    catalog: Catalog = Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    set_world_id(str(world_id))
    world, context, nav, rail_pages = await world_page(db, world_id, user, "storie")
    stories = await list_stories(db, world_id, user)
    published, drafts = split_published_drafts(stories)
    return catalog.render(
        "pages.stories.StoryList",
        world=world,
        world_context=context,
        nav=nav,
        pages=rail_pages,
        stories=published,
        drafts=drafts,
        can_manage=await is_master(db, world, user),
        crumbs=_crumbs(world),
        current_user=user,
    )


async def _form_context(db, world_id, user, story):
    world, context, nav, rail_pages = await world_page(db, world_id, user, "storie")
    await master_world(db, world_id, user)
    sessions = await list_sessions(db, world_id, user)
    options = [
        Option(
            value=str(session.id), label=f"{session.in_world_date} · {session.title}"
        )
        for session in sessions
    ]
    return world, context, nav, rail_pages, options


@router.get("/worlds/{world_id}/stories/new")
async def story_new_page(world_id: uuid.UUID) -> RedirectResponse:
    return RedirectResponse(f"/worlds/{world_id}/stories", status_code=303)


@router.post("/worlds/{world_id}/stories/new")
async def story_new_submit(
    world_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
) -> Response:
    story = await create_story(
        db, world_id, StoryCreate(title="Nuova storia", is_draft=True), user
    )
    return _htmx_redirect(f"/worlds/{world_id}/stories/{story.id}?edit=1")


@router.get("/worlds/{world_id}/stories/{story_id}", response_class=HTMLResponse)
async def story_detail_page(
    world_id: uuid.UUID,
    story_id: uuid.UUID,
    edit: bool = False,
    catalog: Catalog = Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    set_world_id(str(world_id))
    world, context, nav, rail_pages = await world_page(db, world_id, user, "storie")
    story = await get_story(db, world_id, story_id, user)
    short_html, body_html, links = await render_document(
        db, world_id, ContentKind.STORY, story
    )
    sessions = await list_sessions(db, world_id, user)
    session_options = [
        Option(
            value=str(session.id), label=f"{session.in_world_date} · {session.title}"
        )
        for session in sessions
    ]
    return catalog.render(
        "pages.stories.StoryDetail",
        world=world,
        world_context=context,
        nav=nav,
        pages=rail_pages,
        story=story,
        metadata=[
            MetadataField(
                name="period_label",
                label="Periodo",
                kind="text",
                value=story.period_label,
            ),
            MetadataField(
                name="status",
                label="Stato",
                kind="select",
                value=story.status.value,
                options=_STATUS_OPTIONS,
            ),
            MetadataField(
                name="session_ids",
                label="Sessioni",
                kind="multiselect",
                values=[str(session.id) for session in story.sessions],
                options=session_options,
            ),
            MetadataField(
                name="tint",
                label="Colore",
                kind="tint",
                value=story.tint,
                options=tint_options(),
            ),
        ],
        auto_edit=edit,
        short_html=short_html,
        body_html=body_html,
        links=links,
        can_manage=await is_master(db, world, user),
        crumbs=_crumbs(world, Crumb(label=story.title)),
        current_user=user,
    )


@router.get("/worlds/{world_id}/stories/{story_id}/edit")
async def story_edit_page(world_id: uuid.UUID, story_id: uuid.UUID) -> RedirectResponse:
    return RedirectResponse(
        f"/worlds/{world_id}/stories/{story_id}?edit=1", status_code=303
    )


@router.post("/worlds/{world_id}/stories/{story_id}/cancel-draft")
async def story_cancel_draft(
    world_id: uuid.UUID,
    story_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
) -> Response:
    story = await get_story(db, world_id, story_id, user)
    require_draft(story)
    await delete_story(db, world_id, story_id, user)
    return _htmx_redirect(f"/worlds/{world_id}/stories")


@router.delete("/worlds/{world_id}/stories/{story_id}")
async def story_delete(
    world_id: uuid.UUID,
    story_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
) -> Response:
    await delete_story(db, world_id, story_id, user)
    return _htmx_redirect(f"/worlds/{world_id}/stories")
