"""The world overview: where are we now.

Counts, the campaign diary, the open story arc and the clearing the party is in.
Content features register their own count query here as they land, so the
overview never reaches into another feature's tables directly.
"""

from collections.abc import Awaitable, Callable
import uuid

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..navigation import TimelineEntry
from .models import WorldModel

CountFn = Callable[[AsyncSession, uuid.UUID], Awaitable[int]]

# section id -> count query, filled in by each content feature.
_COUNTERS: dict[str, CountFn] = {}


def register_counter(section: str, fn: CountFn) -> None:
    _COUNTERS[section] = fn


class Teaser(BaseModel):
    """A compact card for the open story or the current clearing."""

    kind: str
    title: str
    href: str
    description: str
    tint: str | None = None
    meta: str | None = None


class WorldOverview(BaseModel):
    counts: dict[str, int]
    diary: list[TimelineEntry]
    open_story: Teaser | None = None
    current_place: Teaser | None = None


async def build_overview(db: AsyncSession, world: WorldModel) -> WorldOverview:
    counts = {section: await fn(db, world.id) for section, fn in _COUNTERS.items()}
    return WorldOverview(
        counts=counts,
        diary=await _diary(db, world),
        open_story=await _open_story(db, world),
        current_place=await _current_place(db, world),
    )


async def _diary(db: AsyncSession, world: WorldModel) -> list[TimelineEntry]:
    """The last four sessions, most recent first."""
    return []


async def _open_story(db: AsyncSession, world: WorldModel) -> Teaser | None:
    return None


async def _current_place(db: AsyncSession, world: WorldModel) -> Teaser | None:
    return None
