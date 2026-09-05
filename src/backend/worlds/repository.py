import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload, selectinload

from ..users.models import UserModel
from .models import WorldModel
from .schemas import WorldCreate, WorldUpdate


class WorldRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_users(self, user_ids: list[uuid.UUID]) -> list[UserModel]:
        if not user_ids:
            return []
        users = list(
            (
                await self.db.scalars(
                    select(UserModel).where(UserModel.id.in_(user_ids))
                )
            ).all()
        )
        if len(users) != len(set(user_ids)):
            raise ValueError("One or more shared users do not exist")
        return users

    @staticmethod
    def _visible(user_id: uuid.UUID):
        return or_(
            WorldModel.created_by_id == user_id,
            WorldModel.shared_with.any(UserModel.id == user_id),
        )

    @staticmethod
    def _options(include_shared_with: bool):
        return (
            selectinload(WorldModel.created_by),
            selectinload(WorldModel.shared_with)
            if include_shared_with
            else noload(WorldModel.shared_with),
        )

    async def create(self, data: WorldCreate, created_by_id: uuid.UUID) -> WorldModel:
        created_by = await self.db.get(UserModel, created_by_id)
        if created_by is None:
            raise ValueError("Creator does not exist")
        world = WorldModel(
            name=data.name,
            description=data.description,
            created_by=created_by,
            shared_with=await self._get_users(data.shared_with),
        )
        self.db.add(world)
        await self.db.flush()
        return world

    async def get(
        self,
        world_id: uuid.UUID,
        user_id: uuid.UUID,
        is_admin: bool,
        include_shared_with: bool = False,
    ) -> WorldModel | None:
        stmt = (
            select(WorldModel)
            .options(*self._options(include_shared_with))
            .where(WorldModel.id == world_id)
        )
        if not is_admin:
            stmt = stmt.where(self._visible(user_id))
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_page(
        self,
        user_id: uuid.UUID,
        is_admin: bool,
        page: int,
        page_size: int,
        include_shared_with: bool = False,
    ) -> tuple[list[WorldModel], int]:
        if page < 1 or page_size < 1:
            raise ValueError("page and page_size must be positive")
        visibility = self._visible(user_id)
        count_stmt = select(func.count()).select_from(WorldModel)
        stmt = select(WorldModel).options(*self._options(include_shared_with))
        if not is_admin:
            count_stmt = count_stmt.where(visibility)
            stmt = stmt.where(visibility)
        total = await self.db.scalar(count_stmt)
        worlds = list(
            (
                await self.db.scalars(
                    stmt.order_by(WorldModel.created_at.desc(), WorldModel.id.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ).all()
        )
        return worlds, total or 0

    async def update(self, world: WorldModel, data: WorldUpdate) -> WorldModel:
        if data.name is not None:
            world.name = data.name
        if data.description is not None:
            world.description = data.description
        if data.shared_with is not None:
            world.shared_with = await self._get_users(data.shared_with)
        await self.db.flush()
        return world

    async def delete(self, world: WorldModel) -> None:
        await self.db.delete(world)
        await self.db.flush()
