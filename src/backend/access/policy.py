"""Central access policy.

Every content feature resolves a world through one of these helpers instead of
re-implementing the checks, so readable-world, master-required and owner-only
rules stay consistent and testable in one place.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.enums import UserRole
from ..users.schemas import User
from ..worlds.exceptions import WorldAccessDeniedException
from ..worlds.models import WorldModel
from ..worlds.service import get_world, is_master

__all__ = [
    "is_admin",
    "is_owner",
    "readable_world",
    "master_world",
    "owner_world",
]


def is_admin(user: User) -> bool:
    return user.role == UserRole.ADMIN


def is_owner(world: WorldModel, user: User) -> bool:
    return world.created_by_id == user.id


async def readable_world(
    db: AsyncSession,
    world_id: uuid.UUID,
    user: User,
    *,
    include_members: bool = False,
    include_image: bool = False,
) -> WorldModel:
    """Return a world the user may read, or raise 404 if it is not visible.

    Invisible and non-existent worlds are both reported as not found, so the
    API never reveals whether another user's world exists (cross-world IDOR).
    """
    return await get_world(
        db,
        world_id,
        user,
        include_members=include_members,
        include_image=include_image,
    )


async def master_world(
    db: AsyncSession,
    world_id: uuid.UUID,
    user: User,
    *,
    include_members: bool = False,
    include_image: bool = False,
) -> WorldModel:
    """Return a readable world the user masters, or raise 403."""
    world = await readable_world(
        db,
        world_id,
        user,
        include_members=include_members,
        include_image=include_image,
    )
    if not await is_master(db, world, user):
        raise WorldAccessDeniedException(world_id)
    return world


async def owner_world(
    db: AsyncSession,
    world_id: uuid.UUID,
    user: User,
    *,
    include_members: bool = False,
    include_image: bool = False,
) -> WorldModel:
    """Return a readable world the user owns (or administers), or raise 403."""
    world = await readable_world(
        db,
        world_id,
        user,
        include_members=include_members,
        include_image=include_image,
    )
    if not is_admin(user) and not is_owner(world, user):
        raise WorldAccessDeniedException(world_id)
    return world
