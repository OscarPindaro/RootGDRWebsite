"""Resolve ``@[label]`` references and maintain the backlinks index."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TypeAlias

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

ContentModel: TypeAlias = (
    CharacterModel | NpcModel | PageModel | PlaceModel | SessionModel | StoryModel
)
ContentModelType: TypeAlias = type[
    CharacterModel | NpcModel | PageModel | PlaceModel | SessionModel | StoryModel
]

# Used by maintenance commands that need to iterate over every content table.
KIND_MODELS: dict[ContentKind, tuple[ContentModelType, str]] = {
    ContentKind.CHARACTER: (CharacterModel, "characters"),
    ContentKind.NPC: (NpcModel, "npcs"),
    ContentKind.PLACE: (PlaceModel, "places"),
    ContentKind.SESSION: (SessionModel, "sessions"),
    ContentKind.STORY: (StoryModel, "stories"),
    ContentKind.PAGE: (PageModel, "pages"),
}


def content_name(item: ContentModel) -> str:
    if isinstance(item, (CharacterModel, NpcModel, PlaceModel)):
        return item.name
    return item.title


def content_href(kind: ContentKind, world_id: uuid.UUID, item: ContentModel) -> str:
    if isinstance(item, PageModel):
        return f"/worlds/{world_id}/pages/{item.slug}"
    section = KIND_MODELS[kind][1]
    return f"/worlds/{world_id}/{section}/{item.id}"


def _target(
    kind: ContentKind, world_id: uuid.UUID, item: ContentModel
) -> MentionTarget:
    return MentionTarget(
        id=item.id,
        kind=kind,
        tint=item.tint,
        href=content_href(kind, world_id, item),
        name=content_name(item),
    )


async def _matches(
    db: AsyncSession, world_id: uuid.UUID, kind: ContentKind, name: str
) -> list[ContentModel]:
    if kind == ContentKind.CHARACTER:
        return list(
            (
                await db.scalars(
                    select(CharacterModel).where(
                        CharacterModel.world_id == world_id,
                        CharacterModel.name == name,
                    )
                )
            ).all()
        )
    if kind == ContentKind.NPC:
        return list(
            (
                await db.scalars(
                    select(NpcModel).where(
                        NpcModel.world_id == world_id, NpcModel.name == name
                    )
                )
            ).all()
        )
    if kind == ContentKind.PLACE:
        return list(
            (
                await db.scalars(
                    select(PlaceModel).where(
                        PlaceModel.world_id == world_id, PlaceModel.name == name
                    )
                )
            ).all()
        )
    if kind == ContentKind.SESSION:
        return list(
            (
                await db.scalars(
                    select(SessionModel).where(
                        SessionModel.world_id == world_id, SessionModel.title == name
                    )
                )
            ).all()
        )
    if kind == ContentKind.STORY:
        return list(
            (
                await db.scalars(
                    select(StoryModel).where(
                        StoryModel.world_id == world_id, StoryModel.title == name
                    )
                )
            ).all()
        )
    return list(
        (
            await db.scalars(
                select(PageModel).where(
                    PageModel.world_id == world_id, PageModel.title == name
                )
            )
        ).all()
    )


async def resolve_label(
    db: AsyncSession, world_id: uuid.UUID, label: str
) -> MentionTarget | None:
    """Resolve one label. Ambiguous or unknown labels remain placeholders."""
    kind_name, separator, remainder = label.partition(":")
    explicit = next(
        (kind for kind in ContentKind if separator and kind.value == kind_name), None
    )
    name = remainder.strip() if explicit else label.strip()
    kinds = [explicit] if explicit else list(ContentKind)
    found: list[MentionTarget] = []
    for kind in kinds:
        for item in await _matches(db, world_id, kind, name):
            found.append(_target(kind, world_id, item))
    return found[0] if len(found) == 1 else None


async def resolve_text(
    db: AsyncSession, world_id: uuid.UUID, text: str
) -> dict[str, MentionTarget | None]:
    """Resolve every label in Markdown for the renderer's lookup map."""
    return {
        label: await resolve_label(db, world_id, label)
        for label in mention_labels(text)
    }


# Kept as a descriptive alias for body callers and third-party imports.
resolve_body = resolve_text


def document_labels(short_description: str, body: str) -> list[str]:
    """Distinct labels from both Markdown fields, preserving first occurrence."""
    labels: list[str] = []
    for text in (short_description, body):
        for label in mention_labels(text):
            if label not in labels:
                labels.append(label)
    return labels


async def refresh_references(
    db: AsyncSession,
    world_id: uuid.UUID,
    source_kind: ContentKind,
    source_id: uuid.UUID,
    short_description: str,
    body: str,
) -> None:
    """Replace references for one document, scanning summary and body."""
    await db.execute(
        delete(ReferenceModel).where(
            ReferenceModel.source_kind == source_kind.value,
            ReferenceModel.source_id == source_id,
        )
    )
    for label in document_labels(short_description, body):
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


@dataclass(frozen=True)
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
    """Return documents that mention this item, grouped by source kind."""
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
        model = KIND_MODELS[source_kind][0]
        item = await db.get(model, row.source_id)
        if item is None:
            continue
        grouped.setdefault(source_kind, []).append(
            Backlink(
                kind=source_kind,
                name=content_name(item),
                href=content_href(source_kind, world_id, item),
                tint=item.tint,
            )
        )
    return grouped
