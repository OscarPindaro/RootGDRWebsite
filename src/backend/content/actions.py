"""Shared lock / publish toggles for every content document.

One route serves all six content types: the button posts the desired value and
the server flips it through the feature's own update service, so authorization
stays in the service layer.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import HTMLResponse
from jinjax.catalog import Catalog
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..access import readable_world
from ..auth.dependencies import get_current_user
from ..characters.models import CharacterModel
from ..characters.schemas import CharacterUpdate
from ..characters.service import get_character, update_character
from ..dependencies import get_catalog_dep, get_db_session
from ..npcs.models import NpcModel
from ..npcs.schemas import NpcUpdate
from ..npcs.service import get_npc, update_npc
from ..pages.models import PageModel
from ..pages.schemas import PageUpdate
from ..pages.service import get_page, update_page
from ..places.models import PlaceModel
from ..places.schemas import PlaceUpdate
from ..places.service import get_place, update_place
from ..schemas import AppBaseModel, ListResponse
from ..sessions.models import SessionModel
from ..sessions.schemas import SessionUpdate
from ..sessions.service import get_session, update_session
from ..stories.models import StoryModel
from ..stories.schemas import StoryUpdate
from ..stories.service import get_story, update_story
from ..users.schemas import User
from ..worlds.views import _htmx_redirect
from .markdown import render_markdown
from .constants import ContentKind
from .references import resolve_text

router = APIRouter(tags=["content-actions"])

_KINDS = {"characters", "npcs", "places", "sessions", "stories", "pages"}
_FIELDS = {"locked", "is_draft"}


@router.post("/worlds/{world_id}/{kind}/{item_id}/toggle/{field}")
async def toggle_document(
    world_id: uuid.UUID,
    kind: str,
    item_id: uuid.UUID,
    field: str,
    value: bool = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> Response:
    """Lock/unlock or publish/draft a document (owner or master, per feature)."""
    if kind not in _KINDS or field not in _FIELDS:
        return _htmx_redirect(f"/worlds/{world_id}")

    if kind == "characters":
        current = await get_character(db, world_id, item_id, user)
        data = CharacterUpdate(expected_version=current.version)
        if field == "locked":
            data.locked = value
        else:
            data.is_draft = value
        item = await update_character(db, world_id, item_id, data, user)
        return _htmx_redirect(f"/worlds/{world_id}/characters/{item.id}")
    if kind == "npcs":
        current = await get_npc(db, world_id, item_id, user)
        data = NpcUpdate(expected_version=current.version)
        if field == "locked":
            data.locked = value
        else:
            data.is_draft = value
        item = await update_npc(db, world_id, item_id, data, user)
        return _htmx_redirect(f"/worlds/{world_id}/npcs/{item.id}")
    if kind == "places":
        current = await get_place(db, world_id, item_id, user)
        data = PlaceUpdate(expected_version=current.version)
        if field == "locked":
            data.locked = value
        else:
            data.is_draft = value
        item = await update_place(db, world_id, item_id, data, user)
        return _htmx_redirect(f"/worlds/{world_id}/places/{item.id}")
    if kind == "sessions":
        current = await get_session(db, world_id, item_id, user)
        data = SessionUpdate(expected_version=current.version)
        if field == "locked":
            data.locked = value
        else:
            data.is_draft = value
        item = await update_session(db, world_id, item_id, data, user)
        return _htmx_redirect(f"/worlds/{world_id}/sessions/{item.id}")
    if kind == "stories":
        current = await get_story(db, world_id, item_id, user)
        data = StoryUpdate(expected_version=current.version)
        if field == "locked":
            data.locked = value
        else:
            data.is_draft = value
        item = await update_story(db, world_id, item_id, data, user)
        return _htmx_redirect(f"/worlds/{world_id}/stories/{item.id}")

    current_page = await get_page(db, world_id, item_id, user)
    page_data = PageUpdate(expected_version=current_page.version)
    if field == "locked":
        page_data.locked = value
    else:
        page_data.is_draft = value
    page = await update_page(db, world_id, item_id, page_data, user)
    return _htmx_redirect(f"/worlds/{world_id}/pages/{page.slug}")


_CONFIRM_ACTIONS = {"delete", "cancel-draft"}


async def _document_label(
    db: AsyncSession, world_id: uuid.UUID, kind: str, item_id: uuid.UUID, user: User
) -> str:
    """The name a confirmation names: a document's name, or its title."""
    if kind == "characters":
        return (await get_character(db, world_id, item_id, user)).name
    if kind == "npcs":
        return (await get_npc(db, world_id, item_id, user)).name
    if kind == "places":
        return (await get_place(db, world_id, item_id, user)).name
    if kind == "sessions":
        return (await get_session(db, world_id, item_id, user)).title
    if kind == "stories":
        return (await get_story(db, world_id, item_id, user)).title
    return (await get_page(db, world_id, item_id, user)).title


@router.get(
    "/worlds/{world_id}/{kind}/{item_id}/confirm/{action}", response_class=HTMLResponse
)
async def document_action_confirm(
    world_id: uuid.UUID,
    kind: str,
    item_id: uuid.UUID,
    action: str,
    catalog: Catalog = Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Return the delete/cancel-draft confirmation for the shared dialog.

    Authorization is not repeated here: this fragment only renders a document's
    own name, which the reader can already see, and the mutation route it
    forwards to enforces the same manage permission as every other write.
    """
    if kind not in _KINDS or action not in _CONFIRM_ACTIONS:
        raise HTTPException(status_code=404, detail="Unknown document action")
    label = await _document_label(db, world_id, kind, item_id, user)
    if action == "delete":
        title, message, confirm_label = (
            "Elimina",
            f"Eliminare «{label}»?",
            "Elimina",
        )
        request = {"hx-delete": f"/worlds/{world_id}/{kind}/{item_id}"}
    else:
        title, message, confirm_label = (
            "Annulla bozza",
            "Annullare questa bozza?",
            "Annulla bozza",
        )
        request = {"hx-post": f"/worlds/{world_id}/{kind}/{item_id}/cancel-draft"}
    return catalog.render(
        "common.ConfirmDialog",
        title=title,
        message=message,
        confirm_label=confirm_label,
        confirm_variant="danger",
        confirm_icon="trash-2",
        _attrs=request,
    )


class MentionSuggestion(AppBaseModel):
    name: Annotated[str, Field(description="Display name")]
    kind: Annotated[ContentKind, Field(description="Content kind")]
    tint: Annotated[str, Field(description="Tint token")]
    insert: Annotated[str, Field(description="Unambiguous mention label")]


class PreviewRequest(AppBaseModel):
    """One Markdown field to render with the authoritative server renderer."""

    body: Annotated[str, Field(default="", max_length=100_000)]
    short_description: Annotated[str | None, Field(default=None, max_length=1000)]


@router.get(
    "/api/worlds/{world_id}/mentions",
    response_model=ListResponse[MentionSuggestion],
)
async def mention_suggestions(
    world_id: uuid.UUID,
    q: Annotated[str, Query(max_length=255)] = "",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> ListResponse[MentionSuggestion]:
    """Fuzzy-enough suggestions for the editor's ``@`` menu."""
    await readable_world(db, world_id, user)
    matches: list[tuple[str, ContentKind, str]] = []
    character_stmt = select(CharacterModel).where(
        CharacterModel.world_id == world_id, CharacterModel.name.ilike(f"%{q}%")
    )
    npc_stmt = select(NpcModel).where(
        NpcModel.world_id == world_id, NpcModel.name.ilike(f"%{q}%")
    )
    place_stmt = select(PlaceModel).where(
        PlaceModel.world_id == world_id, PlaceModel.name.ilike(f"%{q}%")
    )
    session_stmt = select(SessionModel).where(
        SessionModel.world_id == world_id, SessionModel.title.ilike(f"%{q}%")
    )
    story_stmt = select(StoryModel).where(
        StoryModel.world_id == world_id, StoryModel.title.ilike(f"%{q}%")
    )
    page_stmt = select(PageModel).where(
        PageModel.world_id == world_id, PageModel.title.ilike(f"%{q}%")
    )
    matches.extend(
        (item.name, ContentKind.CHARACTER, item.tint)
        for item in (await db.scalars(character_stmt)).all()
    )
    matches.extend(
        (item.name, ContentKind.NPC, item.tint)
        for item in (await db.scalars(npc_stmt)).all()
    )
    matches.extend(
        (item.name, ContentKind.PLACE, item.tint)
        for item in (await db.scalars(place_stmt)).all()
    )
    matches.extend(
        (item.title, ContentKind.SESSION, item.tint)
        for item in (await db.scalars(session_stmt)).all()
    )
    matches.extend(
        (item.title, ContentKind.STORY, item.tint)
        for item in (await db.scalars(story_stmt)).all()
    )
    matches.extend(
        (item.title, ContentKind.PAGE, item.tint)
        for item in (await db.scalars(page_stmt)).all()
    )
    suggestions = [
        MentionSuggestion(
            name=name,
            kind=kind,
            tint=tint,
            insert=(
                f"{kind.value}:{name}"
                if sum(candidate_name == name for candidate_name, _, _ in matches) > 1
                else name
            ),
        )
        for name, kind, tint in matches[:8]
    ]
    return ListResponse(data=suggestions)


@router.post("/worlds/{world_id}/preview", response_class=HTMLResponse)
async def preview_body(
    world_id: uuid.UUID,
    data: PreviewRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> HTMLResponse:
    """Render a body with the server's renderer, for the editor preview tab."""
    await readable_world(db, world_id, user)
    text = data.short_description if data.short_description is not None else data.body
    mentions = await resolve_text(db, world_id, text)
    return HTMLResponse(str(render_markdown(text, mentions)))
