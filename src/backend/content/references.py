"""Resolve `@[label]` references and maintain the DB-backed backlinks index."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..characters.models import CharacterModel
from ..npcs.models import NpcModel
from ..pages.models import PageModel
from ..places.models import PlaceModel
from ..sessions.models import SessionModel
from ..stories.models import StoryModel
from .constants import ContentKind
from .markdown import MentionTarget, mention_labels
from .models import ReferenceModel

# kind -> (model, section path used in URLs)
KIND_MODELS = {
    ContentKind.CHARACTER: (CharacterModel, "characters"),
    ContentKind.NPC: (NpcModel, "npcs"),
    ContentKind.PLACE: (PlaceModel, "luoghi"),
    ContentKind.SESSION: (SessionModel, "sessioni"),
    ContentKind.STORY: (StoryModel, "storie"),
    ContentKind.PAGE: (PageModel, "pagine"),
}

_NAME_FIELD = {
    ContentKind.CHARACTER: "name",
    ContentKind.NPC: "name",
    ContentKind.PLACE: "name",
    ContentKind.SESSION: "title",
    ContentKind.STORY: "title",
    ContentKind.PAGE: "title",
}


def _href(kind: ContentKind, world_id: uuid.UUID, item) -> str:
    _, section = KIND_MODELS[kind]
    if kind == ContentKind.PAGE:
        return f"/worlds/{world_id}/pagine/{item.slug}"
    return f"/worlds/{world_id}/{section}/{item.id}"


def _target(kind: ContentKind, world_id: uuid.UUID, item) -> MentionTarget:
    return MentionTarget(
        id=item.id,
        kind=kind,
        tint=item.tint,
        href=_href(kind, world_id, item),
        name=getattr(item, _NAME_FIELD[kind]),
    )


async def _matches(
    db: AsyncSession, world_id: uuid.UUID, kind: ContentKind, name: str
) -> list:
    model, _ = KIND_MODELS[kind]
    field = getattr(model, _NAME_FIELD[kind])
    return list(
        (
            await db.scalars(
                select(model).where(model.world_id == world_id, field == name)
            )
        ).all()
    )


async def resolve_label(
    db: AsyncSession, world_id: uuid.UUID, label: str
) -> MentionTarget | None:
    """Resolve one label. Ambiguous or unknown labels resolve to ``None``."""
    kind_name, _, rest = label.partition(":")
    explicit: ContentKind | None = None
    if rest and kind_name in {k.value for k in ContentKind}:
        explicit = ContentKind(kind_name)
        name = rest.strip()
    else:
        name = label.strip()

    kinds = [explicit] if explicit else list(ContentKind)
    found: list[MentionTarget] = []
    for kind in kinds:
        for item in await _matches(db, world_id, kind, name):
            found.append(_target(kind, world_id, item))
    if len(found) == 1:
        return found[0]
    return None


async def resolve_body(
    db: AsyncSession, world_id: uuid.UUID, body: str
) -> dict[str, MentionTarget | None]:
    """Resolve every label in a body, for the renderer's lookup map."""
    return {
        label: await resolve_label(db, world_id, label)
        for label in mention_labels(body)
    }


async def refresh_references(
    db: AsyncSession,
    world_id: uuid.UUID,
    source_kind: ContentKind,
    source_id: uuid.UUID,
    body: str,
) -> None:
    """Replace the stored reference rows for one document."""
    await db.execute(
        delete(ReferenceModel).where(
            ReferenceModel.source_kind == source_kind.value,
            ReferenceModel.source_id == source_id,
        )
    )
    for label in mention_labels(body):
        target = await resolve_label(db, world_id, label)
        db.add(
            ReferenceModel(
                world_id=world_id,
                source_kind=source_kind.value,
                source_id=source_id,
                label=label,
                target_kind=target.kind.value if target else None,
                target_id=target.id if target else None,
            )
        )
    await db.flush()


@dataclass
class Backlink:
    kind: ContentKind
    name: str
    href: str
    tint: str


async def backlinks(
    db: AsyncSession,
    world_id: uuid.UUID,
    target_kind: ContentKind,
    target_id: uuid.UUID,
) -> dict[ContentKind, list[Backlink]]:
    """Who references this item, grouped by the source kind."""
    rows = list(
        (
            await db.scalars(
                select(ReferenceModel).where(
                    ReferenceModel.world_id == world_id,
                    ReferenceModel.target_kind == target_kind.value,
                    ReferenceModel.target_id == target_id,
                )
            )
        ).all()
    )
    grouped: dict[ContentKind, list[Backlink]] = {}
    for row in rows:
        source_kind = ContentKind(row.source_kind)
        model, _ = KIND_MODELS[source_kind]
        item = await db.get(model, row.source_id)
        if item is None:
            continue
        grouped.setdefault(source_kind, []).append(
            Backlink(
                kind=source_kind,
                name=getattr(item, _NAME_FIELD[source_kind]),
                href=_href(source_kind, world_id, item),
                tint=item.tint,
            )
        )
    return grouped
