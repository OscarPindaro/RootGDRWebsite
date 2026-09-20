"""Shared helpers for the content feature views."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.enums import WorldRole
from ..navigation import NavItem, Option, WorldContext, world_nav
from ..users.schemas import User
from ..worlds.models import WorldModel
from ..worlds.service import role_for_world
from ..access import readable_world
from .constants import ANIMALS, SHAPE_LABELS, SHAPE_NAMES, TINT_LABELS, TINTS


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
) -> tuple[WorldModel, WorldContext, list[NavItem]]:
    """Load the world plus the rail context and navigation for a page."""
    world = await readable_world(db, world_id, user, include_members=True)
    role = role_for_world(world, user)
    label = "Master" if role == WorldRole.MASTER else "Giocatore"
    context = WorldContext(id=str(world.id), name=world.name, role=label)
    return world, context, world_nav(str(world.id), active, counts)


def owner_label(owner_name: str, is_master: bool = False) -> str:
    return f"NPC del Master" if is_master else f"Giocato da {owner_name}"
