import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from ..db.enums import UserRole
from ..log import get_logger
from ..users.schemas import User
from .exceptions import (
    SharedUserNotFoundException,
    WorldAccessDeniedException,
    WorldNotFoundException,
)
from .models import WorldModel
from .repository import WorldRepository
from .schemas import WorldCreate, WorldUpdate

logger = get_logger(__name__)


def _is_admin(user: User) -> bool:
    return user.role == UserRole.ADMIN


async def create_world(db: AsyncSession, data: WorldCreate, user: User) -> WorldModel:
    try:
        world = await WorldRepository(db).create(data, user.id)
    except ValueError as exc:
        raise SharedUserNotFoundException() from exc
    logger.info("World created", world_id=world.id, created_by_id=user.id)
    return world


async def get_world(
    db: AsyncSession,
    world_id: uuid.UUID,
    user: User,
    include_shared_with: bool = False,
) -> WorldModel:
    world = await WorldRepository(db).get(
        world_id, user.id, _is_admin(user), include_shared_with
    )
    if world is None:
        raise WorldNotFoundException(world_id)
    return world


async def get_worlds(
    db: AsyncSession,
    user: User,
    page: int = 1,
    page_size: int = 20,
    include_shared_with: bool = False,
) -> tuple[list[WorldModel], int]:
    return await WorldRepository(db).get_page(
        user.id, _is_admin(user), page, page_size, include_shared_with
    )


async def update_world(
    db: AsyncSession,
    world_id: uuid.UUID,
    data: WorldUpdate,
    user: User,
    include_shared_with: bool = False,
) -> WorldModel:
    world = await get_world(db, world_id, user, include_shared_with)
    if not _is_admin(user) and world.created_by_id != user.id:
        raise WorldAccessDeniedException(world_id)
    try:
        updated = await WorldRepository(db).update(world, data)
    except ValueError as exc:
        raise SharedUserNotFoundException() from exc
    logger.info("World updated", world_id=world_id, updated_by_id=user.id)
    return updated


async def delete_world(db: AsyncSession, world_id: uuid.UUID, user: User) -> None:
    world = await get_world(db, world_id, user)
    if not _is_admin(user) and world.created_by_id != user.id:
        raise WorldAccessDeniedException(world_id)
    await WorldRepository(db).delete(world)
    logger.info("World deleted", world_id=world_id, deleted_by_id=user.id)
