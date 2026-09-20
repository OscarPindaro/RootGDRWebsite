"""Command palette search.

Results come from the database on every query — no process-local index — and
create actions are only offered when the viewer is allowed to use them.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .access import readable_world
from .auth.dependencies import get_current_user
from .content.constants import KIND_LABELS, ContentKind
from .content.references import _NAME_FIELD, KIND_MODELS
from .dependencies import get_db_session
from .schemas import AppBaseModel, ListResponse
from .users.schemas import User
from .worlds.service import get_worlds, is_master

router = APIRouter(tags=["palette"])


class PaletteItem(AppBaseModel):
    kind: Annotated[str, Field(description="Grouping label")]
    name: Annotated[str, Field(description="Display name")]
    href: Annotated[str, Field(description="Navigation target")]


def _href(world_id: uuid.UUID, kind: ContentKind, item) -> str:
    _, section = KIND_MODELS[kind]
    if kind == ContentKind.PAGE:
        return f"/worlds/{world_id}/pages/{item.slug}"
    return f"/worlds/{world_id}/{section}/{item.id}"


@router.get("/api/palette", response_model=ListResponse[PaletteItem])
async def palette(
    q: Annotated[str, Query(max_length=255)] = "",
    world_id: Annotated[uuid.UUID | None, Query()] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ListResponse[PaletteItem]:
    """Search worlds, the current world's content, and allowed create actions."""
    items: list[PaletteItem] = []

    worlds, _ = await get_worlds(db, user, page=1, page_size=8)
    for world in worlds:
        if q.lower() in world.name.lower():
            items.append(
                PaletteItem(kind="Mondo", name=world.name, href=f"/worlds/{world.id}")
            )

    if world_id is not None:
        world = await readable_world(db, world_id, user)
        for kind, (model, _) in KIND_MODELS.items():
            field = getattr(model, _NAME_FIELD[kind])
            stmt = (
                select(model)
                .where(model.world_id == world_id, field.ilike(f"%{q}%"))
                .limit(5)
            )
            for item in (await db.scalars(stmt)).all():
                items.append(
                    PaletteItem(
                        kind=KIND_LABELS[kind],
                        name=getattr(item, _NAME_FIELD[kind]),
                        href=_href(world_id, kind, item),
                    )
                )
        if await is_master(db, world, user):
            items.extend(
                [
                    PaletteItem(
                        kind="Azione",
                        name="Nuova sessione",
                        href=f"/worlds/{world_id}/sessions/new",
                    ),
                    PaletteItem(
                        kind="Azione",
                        name="Nuovo luogo",
                        href=f"/worlds/{world_id}/places/new",
                    ),
                    PaletteItem(
                        kind="Azione",
                        name="Nuovo personaggio",
                        href=f"/worlds/{world_id}/characters/new",
                    ),
                    PaletteItem(
                        kind="Azione",
                        name="Nuovo NPC",
                        href=f"/worlds/{world_id}/npcs/new",
                    ),
                    PaletteItem(
                        kind="Azione",
                        name="Nuova storia",
                        href=f"/worlds/{world_id}/stories/new",
                    ),
                    PaletteItem(
                        kind="Azione",
                        name="Nuova pagina",
                        href=f"/worlds/{world_id}/pages/new",
                    ),
                ]
            )

    return ListResponse(data=items[:12])
