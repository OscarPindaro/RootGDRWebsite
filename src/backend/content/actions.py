"""Shared lock / publish toggles for every content document.

One route serves all six content types: the button posts the desired value and
the server flips it through the feature's own update service, so authorization
stays in the service layer.
"""

import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, Query, Response
from fastapi.responses import HTMLResponse
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..access import readable_world
from ..auth.dependencies import get_current_user
from ..characters.schemas import CharacterUpdate
from ..characters.service import update_character
from ..dependencies import get_db_session
from ..npcs.schemas import NpcUpdate
from ..npcs.service import update_npc
from ..pages.schemas import PageUpdate
from ..pages.service import update_page
from ..places.schemas import PlaceUpdate
from ..places.service import update_place
from ..schemas import AppBaseModel, ListResponse
from ..sessions.schemas import SessionUpdate
from ..sessions.service import update_session
from ..stories.schemas import StoryUpdate
from ..stories.service import update_story
from ..users.schemas import User
from ..worlds.views import _htmx_redirect
from .markdown import render_markdown
from .references import _NAME_FIELD, KIND_MODELS, resolve_body

router = APIRouter(tags=["content-actions"])

UpdateFn = Callable[..., Awaitable[Any]]

_UPDATERS: dict[str, tuple[UpdateFn, type]] = {
    "characters": (update_character, CharacterUpdate),
    "npcs": (update_npc, NpcUpdate),
    "luoghi": (update_place, PlaceUpdate),
    "sessioni": (update_session, SessionUpdate),
    "storie": (update_story, StoryUpdate),
    "pagine": (update_page, PageUpdate),
}

_FIELDS = {"locked", "is_draft"}


def _detail_url(kind: str, world_id: uuid.UUID, item: Any) -> str:
    if kind == "pagine":
        return f"/worlds/{world_id}/pagine/{item.slug}"
    return f"/worlds/{world_id}/{kind}/{item.id}"


@router.post("/worlds/{world_id}/{kind}/{item_id}/toggle/{field}")
async def toggle_document(
    world_id: uuid.UUID,
    kind: str,
    item_id: uuid.UUID,
    field: str,
    value: bool = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    """Lock/unlock or publish/draft a document (owner or master, per feature)."""
    if kind not in _UPDATERS or field not in _FIELDS:
        return _htmx_redirect(f"/worlds/{world_id}")
    updater, schema = _UPDATERS[kind]
    item = await updater(db, world_id, item_id, schema(**{field: value}), user)
    return _htmx_redirect(_detail_url(kind, world_id, item))


class MentionSuggestion(AppBaseModel):
    name: Annotated[str, Field(description="Display name")]
    kind: Annotated[str, Field(description="Content kind")]
    tint: Annotated[str, Field(description="Tint token")]


@router.get(
    "/api/worlds/{world_id}/mentions",
    response_model=ListResponse[MentionSuggestion],
)
async def mention_suggestions(
    world_id: uuid.UUID,
    q: Annotated[str, Query(max_length=255)] = "",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
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
    body: Annotated[str, Form()] = "",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> HTMLResponse:
    """Render a body with the server's renderer, for the editor preview tab."""
    await readable_world(db, world_id, user)
    mentions = await resolve_body(db, world_id, body)
    return HTMLResponse(str(render_markdown(body, mentions)))
