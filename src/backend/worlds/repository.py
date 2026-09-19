import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload, selectinload

from ..db.enums import WorldRole
from ..users.models import UserModel
from .models import WorldMembershipModel, WorldModel
from .schemas import WorldCreate, WorldMemberInput, WorldUpdate


class WorldRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _resolve_members(
        self, entries: list[WorldMemberInput], owner_id: uuid.UUID
    ) -> list[WorldMembershipModel]:
        """Build membership rows, validating that every user exists.

        The owner is always present as a master and wins over any conflicting
        entry, so a payload can never demote or drop the owner.
        """
        by_user: dict[uuid.UUID, WorldRole] = {}
        for entry in entries:
            by_user[entry.user_id] = WorldRole(entry.role)
        by_user[owner_id] = WorldRole.MASTER

        user_ids = list(by_user)
        users = list(
            (
                await self.db.scalars(
                    select(UserModel).where(UserModel.id.in_(user_ids))
                )
            ).all()
        )
        if len(users) != len(user_ids):
            raise ValueError("One or more members do not exist")
        return [
            WorldMembershipModel(user_id=user.id, role=by_user[user.id], user=user)
            for user in users
        ]

    @staticmethod
    def _visible(user_id: uuid.UUID):
        return or_(
            WorldModel.created_by_id == user_id,
            WorldModel.memberships.any(WorldMembershipModel.user_id == user_id),
        )

    @staticmethod
    def _options(include_members: bool, include_image: bool = False):
        return (
            selectinload(WorldModel.created_by),
            selectinload(WorldModel.memberships).selectinload(WorldMembershipModel.user)
            if include_members
            else noload(WorldModel.memberships),
            selectinload(WorldModel.image)
            if include_image
            else noload(WorldModel.image),
        )

    async def create(self, data: WorldCreate, created_by_id: uuid.UUID) -> WorldModel:
        created_by = await self.db.get(UserModel, created_by_id)
        if created_by is None:
            raise ValueError("Creator does not exist")
        world = WorldModel(
            name=data.name,
            description=data.description,
            created_by=created_by,
        )
        world.memberships = await self._resolve_members(data.members, created_by_id)
        self.db.add(world)
        await self.db.flush()
        return world

    async def get(
        self,
        world_id: uuid.UUID,
        user_id: uuid.UUID,
        is_admin: bool,
        include_members: bool = False,
        include_image: bool = False,
    ) -> WorldModel | None:
        stmt = (
            select(WorldModel)
            .options(*self._options(include_members, include_image))
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
        include_members: bool = False,
    ) -> tuple[list[WorldModel], int]:
        if page < 1 or page_size < 1:
            raise ValueError("page and page_size must be positive")
        visibility = self._visible(user_id)
        count_stmt = select(func.count()).select_from(WorldModel)
        stmt = select(WorldModel).options(*self._options(include_members))
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
        if data.members is not None:
            world.memberships = await self._resolve_members(
                data.members, world.created_by_id
            )
        await self.db.flush()
        return world

    async def get_membership(
        self, world_id: uuid.UUID, user_id: uuid.UUID
    ) -> WorldMembershipModel | None:
        return (
            await self.db.execute(
                select(WorldMembershipModel).where(
                    WorldMembershipModel.world_id == world_id,
                    WorldMembershipModel.user_id == user_id,
                )
            )
        ).scalar_one_or_none()

    async def delete(self, world: WorldModel) -> None:
        await self.db.delete(world)
        await self.db.flush()
