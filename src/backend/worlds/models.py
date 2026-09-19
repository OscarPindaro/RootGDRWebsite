import uuid

from sqlalchemy import Enum as SAEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.db import Base
from ..db.enums import WorldRole
from ..db.mixins import TimestampMixin, UUIDv7PrimaryKeyMixin
from ..files.models import FileModel
from ..users.models import UserModel


class WorldMembershipModel(Base, TimestampMixin):
    """A user's role inside a world.

    One row per (world, user), including the owner (who is inserted as a
    master at creation and can never be removed). The role enum is enforced at
    the database level.
    """

    __tablename__ = "world_memberships"

    world_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("worlds.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[WorldRole] = mapped_column(
        SAEnum(WorldRole, name="world_role"), nullable=False
    )

    world: Mapped["WorldModel"] = relationship(back_populates="memberships")
    user: Mapped[UserModel] = relationship(lazy="select")


class WorldModel(Base, UUIDv7PrimaryKeyMixin, TimestampMixin):
    name: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str] = mapped_column(nullable=False)
    image_file_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("files.id", ondelete="SET NULL"), nullable=True
    )
    image: Mapped[FileModel | None] = relationship(foreign_keys=[image_file_id])
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    created_by: Mapped[UserModel] = relationship(
        foreign_keys=[created_by_id], lazy="select"
    )
    memberships: Mapped[list[WorldMembershipModel]] = relationship(
        back_populates="world",
        lazy="select",
        cascade="all, delete-orphan",
    )

    @property
    def image_url(self) -> str | None:
        return f"/api/worlds/{self.id}/image" if self.image_file_id else None
