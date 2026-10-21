"""Command palette search.

Results come from the database on every query — no process-local index — and
create actions are only offered when the viewer is allowed to use them.
"""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import Field
from sqlalchemy import String, cast, func, literal, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from .access import readable_world
from .auth.dependencies import get_current_user
from .config import AppConfig, get_app_config
from .content.constants import KIND_LABELS, ContentKind
from .characters.models import CharacterModel
from .npcs.models import NpcModel
from .pages.models import PageModel
from .places.models import PlaceModel
from .sessions.models import SessionModel
from .stories.models import StoryModel
from .dependencies import get_db_session
from .drawings.models import DrawingModel
from .db.enums import UserRole
from .navigation import WORLD_SECTIONS, visible_features
from .schemas import AppBaseModel, PagedResponse
from .users.schemas import User
from .worlds.models import WorldModel
from .worlds.repository import WorldRepository
from .worlds.service import is_master

router = APIRouter(tags=["palette"])


class PaletteItem(AppBaseModel):
    kind: Annotated[str, Field(description="Grouping label")]
    name: Annotated[str, Field(description="Display name")]
    href: Annotated[str, Field(description="Navigation target", pattern=r"^/[a-zA-Z]")]
    method: Literal["GET", "POST"] = "GET"


@router.get("/api/palette", response_model=PagedResponse[PaletteItem])
async def palette(
    q: Annotated[str, Query(max_length=255)] = "",
    world_id: Annotated[uuid.UUID | None, Query()] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
    page: Annotated[int, Query(ge=1, le=1000)] = 1,
    config: AppConfig = Depends(get_app_config),
) -> PagedResponse[PaletteItem]:
    """Search worlds, the current world's content, and allowed create actions."""
    admin = user.role == UserRole.ADMIN
    term = q.casefold()
    statements = []
    for feature in visible_features(admin, config.env):
        if any(term in value.casefold() for value in (feature.label, *feature.aliases)):
            statements.append(
                select(
                    literal("Sezione").label("kind"),
                    literal(feature.label).label("name"),
                    literal(feature.href).label("href"),
                    literal("GET").label("method"),
                    literal(0).label("rank"),
                )
            )
        if (
            feature.create_name
            and feature.create_href
            and term in feature.create_name.casefold()
        ):
            statements.append(
                select(
                    literal("Crea").label("kind"),
                    literal(feature.create_name).label("name"),
                    literal(feature.create_href).label("href"),
                    literal(feature.create_method).label("method"),
                    literal(1).label("rank"),
                )
            )

    worlds = select(
        literal("Mondo").label("kind"),
        WorldModel.name.label("name"),
        (literal("/worlds/") + cast(WorldModel.id, String)).label("href"),
        literal("GET").label("method"),
        literal(2).label("rank"),
    ).where(WorldModel.name.icontains(q, autoescape=True))
    if not admin:
        worlds = worlds.where(WorldRepository.visible_filter(user.id))
    statements.append(worlds)
    if admin:
        statements.append(
            select(
                literal("Disegno").label("kind"),
                DrawingModel.title.label("name"),
                (literal("/drawings/") + cast(DrawingModel.id, String)).label("href"),
                literal("GET").label("method"),
                literal(3).label("rank"),
            ).where(DrawingModel.title.icontains(q, autoescape=True))
        )

    if world_id is not None:
        world = await readable_world(db, world_id, user)
        master = await is_master(db, world, user)
        for _section, label, _mark, path in WORLD_SECTIONS:
            if path == "npcs" and not master:
                continue
            if path is not None and term in label.casefold():
                statements.append(
                    select(
                        literal("Sezione").label("kind"),
                        literal(label).label("name"),
                        literal(f"/worlds/{world_id}/{path}").label("href"),
                        literal("GET").label("method"),
                        literal(0).label("rank"),
                    )
                )
        named_queries = (
            (
                ContentKind.CHARACTER,
                CharacterModel,
                CharacterModel.name,
                CharacterModel.owner_id,
                "characters",
            ),
            (ContentKind.NPC, NpcModel, NpcModel.name, NpcModel.created_by_id, "npcs"),
            (
                ContentKind.PLACE,
                PlaceModel,
                PlaceModel.name,
                PlaceModel.created_by_id,
                "places",
            ),
            (
                ContentKind.SESSION,
                SessionModel,
                SessionModel.title,
                SessionModel.created_by_id,
                "sessions",
            ),
            (
                ContentKind.STORY,
                StoryModel,
                StoryModel.title,
                StoryModel.created_by_id,
                "stories",
            ),
            (
                ContentKind.PAGE,
                PageModel,
                PageModel.title,
                PageModel.created_by_id,
                "pages",
            ),
        )
        for kind, model, name_column, author_column, path in named_queries:
            identity = PageModel.slug if kind == ContentKind.PAGE else model.id
            statements.append(
                select(
                    literal(KIND_LABELS[kind]).label("kind"),
                    name_column.label("name"),
                    (
                        literal(f"/worlds/{world_id}/{path}/") + cast(identity, String)
                    ).label("href"),
                    literal("GET").label("method"),
                    literal(4).label("rank"),
                ).where(
                    model.world_id == world_id,
                    name_column.icontains(q, autoescape=True),
                    or_(model.is_draft.is_(False), author_column == user.id),
                )
            )
            create_name = {
                ContentKind.CHARACTER: "Nuovo personaggio",
                ContentKind.NPC: "Nuovo NPC",
                ContentKind.PLACE: "Nuovo luogo",
                ContentKind.SESSION: "Nuova sessione",
                ContentKind.STORY: "Nuova storia",
                ContentKind.PAGE: "Nuova pagina",
            }[kind]
            if (
                master or kind == ContentKind.CHARACTER
            ) and term in create_name.casefold():
                statements.append(
                    select(
                        literal("Crea").label("kind"),
                        literal(create_name).label("name"),
                        literal(f"/worlds/{world_id}/{path}/new").label("href"),
                        literal("GET").label("method"),
                        literal(1).label("rank"),
                    )
                )

    results = union_all(*statements).subquery()
    total = await db.scalar(select(func.count()).select_from(results)) or 0
    rows = await db.execute(
        select(results)
        .order_by(results.c.rank, func.lower(results.c.name), results.c.href)
        .offset((page - 1) * 12)
        .limit(12)
    )
    return PagedResponse(
        data=[PaletteItem.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=12,
    )
