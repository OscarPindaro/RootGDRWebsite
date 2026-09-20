"""Shared lock / publish toggles for every content document.

One route serves all six content types: the button posts the desired value and
the server flips it through the feature's own update service, so authorization
stays in the service layer.
"""

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

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
from ..sessions.schemas import SessionUpdate
from ..sessions.service import update_session
from ..stories.schemas import StoryUpdate
from ..stories.service import update_story
from ..users.schemas import User
from ..worlds.views import _htmx_redirect

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
