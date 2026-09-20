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
from ..places.models import PlaceModel
from ..sessions.service import recent_sessions
from ..stories.service import open_story
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
    sessions = await recent_sessions(db, world.id, 4)
    return [
        TimelineEntry(
            when=session.in_world_date,
            title=session.title,
            href=f"/worlds/{world.id}/sessions/{session.id}",
            text=session.short_description,
            tint=session.tint,
        )
        for session in sessions
    ]


async def _open_story(db: AsyncSession, world: WorldModel) -> Teaser | None:
    story = await open_story(db, world.id)
    if story is None:
        return None
    return Teaser(
        kind="In corso" if story.period_label is None else story.period_label,
        title=story.title,
        href=f"/worlds/{world.id}/stories/{story.id}",
        description=story.short_description,
        tint=story.tint,
    )


async def _current_place(db: AsyncSession, world: WorldModel) -> Teaser | None:
    """The clearing the party is currently in, if the master set one."""
    if world.current_place_id is None:
        return None
    place = await db.get(PlaceModel, world.current_place_id)
    if place is None or place.world_id != world.id:
        return None
    return Teaser(
        kind="Luogo",
        title=place.name,
        href=f"/worlds/{world.id}/places/{place.id}",
        description=place.short_description,
        tint=place.tint,
    )
