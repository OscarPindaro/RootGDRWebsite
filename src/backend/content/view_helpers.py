"""Shared helpers for the content feature views."""

import uuid

from markupsafe import Markup
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.enums import WorldRole
from ..navigation import NavItem, Option, PageLink, WorldContext, world_nav
from ..pages.service import rail_pages
from ..users.schemas import User
from ..worlds.models import WorldModel
from ..worlds.service import role_for_world
from ..access import readable_world
from .constants import (
    ANIMALS,
    SHAPE_LABELS,
    SHAPE_NAMES,
    TINT_LABELS,
    TINTS,
    ContentKind,
)
from .markdown import render_markdown
from .references import Backlink, ContentModel, backlinks, resolve_text


def tint_options() -> list[Option]:
    return [Option(value=tint, label=TINT_LABELS[tint]) for tint in TINTS]


def animal_options() -> list[Option]:
    return [Option(value=animal, label=animal) for animal in ANIMALS]


def shape_options() -> list[Option]:
    return [Option(value=shape, label=SHAPE_LABELS[shape]) for shape in SHAPE_NAMES]


async def world_page(
    db: AsyncSession,
    world_id: uuid.UUID,
    user: User,
    active: str | None,
    counts: dict[str, int] | None = None,
) -> tuple[WorldModel, WorldContext, list[NavItem], list[PageLink]]:
    """Load the world plus the rail context, navigation and static pages."""
    world = await readable_world(db, world_id, user, include_members=True)
    role = role_for_world(world, user)
    label = "Master" if role == WorldRole.MASTER else "Giocatore"
    context = WorldContext(id=str(world.id), name=world.name, role=label)
    pages = [
        PageLink(label=page.title, href=f"/worlds/{world.id}/pages/{page.slug}")
        for page in await rail_pages(db, world.id)
    ]
    return world, context, world_nav(str(world.id), active, counts), pages


def owner_label(owner_name: str, is_master: bool = False) -> str:
    return f"NPC del Master" if is_master else f"Giocato da {owner_name}"


def split_published_drafts(items: list) -> tuple[list, list]:
    """Split an already visibility-filtered service result into two sections."""
    published: list = []
    drafts: list = []
    for item in items:
        if item.is_draft:
            drafts.append(item)
        else:
            published.append(item)
    return published, drafts


async def render_document(
    db: AsyncSession, world_id: uuid.UUID, kind: ContentKind, item: ContentModel
) -> tuple[Markup, Markup, dict[ContentKind, list[Backlink]]]:
    """Render both Markdown fields and fetch the document's backlinks."""
    short_mentions = await resolve_text(db, world_id, item.short_description)
    body_mentions = await resolve_text(db, world_id, item.body)
    short_html = render_markdown(item.short_description, short_mentions)
    body_html = render_markdown(item.body, body_mentions)
    links = await backlinks(db, world_id, kind, item.id)
    return short_html, body_html, links
