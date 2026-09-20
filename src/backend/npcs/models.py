import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..content.constants import DEFAULT_ANIMAL
from ..content.models import ContentDocumentMixin, TintedMixin
from ..db.db import Base
from ..db.mixins import OptimisticLockMixin, TimestampMixin, UUIDv7PrimaryKeyMixin
from ..files.models import FileModel
from ..users.models import UserModel


class NpcModel(
    Base,
    UUIDv7PrimaryKeyMixin,
    TimestampMixin,
    OptimisticLockMixin,
    ContentDocumentMixin,
    TintedMixin,
):
    __tablename__ = "npcs"

    world_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("worlds.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    created_by: Mapped[UserModel] = relationship(lazy="select")
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    short_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    animal: Mapped[str] = mapped_column(
        String(16), nullable=False, default=DEFAULT_ANIMAL
    )
    image_file_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("files.id", ondelete="SET NULL"), nullable=True
    )
    image: Mapped[FileModel | None] = relationship(foreign_keys=[image_file_id])

    @property
    def image_url(self) -> str | None:
        if not self.image_file_id:
            return None
        return f"/api/worlds/{self.world_id}/npcs/{self.id}/image"
