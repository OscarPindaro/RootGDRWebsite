import uuid

from sqlalchemy import Column, ForeignKey, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.db import Base
from ..db.mixins import TimestampMixin, UUIDv7PrimaryKeyMixin
from ..files.models import FileModel
from ..users.models import UserModel


world_shared_users = Table(
    "world_shared_users",
    Base.metadata,
    Column("world_id", ForeignKey("worlds.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)


class WorldModel(Base, UUIDv7PrimaryKeyMixin, TimestampMixin):
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
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
    shared_with: Mapped[list[UserModel]] = relationship(
        secondary=world_shared_users, lazy="select"
    )

    @property
    def image_url(self) -> str | None:
        return f"/api/worlds/{self.id}/image" if self.image_file_id else None
