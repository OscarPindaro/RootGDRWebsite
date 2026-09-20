"""Shared lock / publish toggles for every content document.

One route serves all six content types: the button posts the desired value and
the server flips it through the feature's own update service, so authorization
stays in the service layer.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import HTMLResponse
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..access import readable_world
from ..auth.dependencies import get_current_user
from ..characters.schemas import CharacterUpdate
from ..characters.service import get_character, update_character
from ..dependencies import get_db_session
from ..npcs.schemas import NpcUpdate
from ..npcs.service import get_npc, update_npc
from ..pages.schemas import PageUpdate
from ..pages.service import get_page, update_page
from ..places.schemas import PlaceUpdate
from ..places.service import get_place, update_place
from ..schemas import AppBaseModel, ListResponse
from ..sessions.schemas import SessionUpdate
from ..sessions.service import get_session, update_session
from ..stories.schemas import StoryUpdate
from ..stories.service import get_story, update_story
from ..users.schemas import User
from ..worlds.views import _htmx_redirect
from .markdown import render_markdown
from .references import _NAME_FIELD, KIND_MODELS, resolve_body

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


class MentionSuggestion(AppBaseModel):
    name: Annotated[str, Field(description="Display name")]
    kind: Annotated[str, Field(description="Content kind")]
    tint: Annotated[str, Field(description="Tint token")]


class PreviewRequest(AppBaseModel):
    """A document body to render, from the editor's live preview."""

    body: Annotated[str, Field(default="", max_length=100_000)]


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
    suggestions: list[MentionSuggestion] = []
    for kind, (model, _) in KIND_MODELS.items():
        field = getattr(model, _NAME_FIELD[kind])
        stmt = (
            select(model)
            .where(model.world_id == world_id, field.ilike(f"%{q}%"))
            .limit(8)
        )
        for item in (await db.scalars(stmt)).all():
            suggestions.append(
                MentionSuggestion(
                    name=getattr(item, _NAME_FIELD[kind]),
                    kind=kind.value,
                    tint=item.tint,
                )
            )
    return ListResponse(data=suggestions[:8])


@router.post("/worlds/{world_id}/preview", response_class=HTMLResponse)
async def preview_body(
    world_id: uuid.UUID,
    data: PreviewRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> HTMLResponse:
    """Render a body with the server's renderer, for the editor preview tab."""
    await readable_world(db, world_id, user)
    mentions = await resolve_body(db, world_id, data.body)
    return HTMLResponse(str(render_markdown(data.body, mentions)))
