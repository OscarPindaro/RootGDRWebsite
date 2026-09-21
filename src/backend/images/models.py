import uuid
from enum import Enum

from sqlalchemy import (
    CheckConstraint,
    Enum as SAEnum,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.db import Base
from ..db.mixins import TimestampMixin, UUIDv7PrimaryKeyMixin
from ..files.models import FileModel
from ..users.models import UserModel


class ImageOwnerKind(str, Enum):
    WORLD = "world"
    CHARACTER = "character"
    NPC = "npc"
    PLACE = "place"


class ImageRevisionModel(Base, UUIDv7PrimaryKeyMixin, TimestampMixin):
    __tablename__ = "image_revisions"
    __table_args__ = (
        UniqueConstraint("file_id", name="uq_image_revisions_file_id"),
        CheckConstraint(
            "owner_kind <> 'WORLD' OR owner_id = world_id",
            name="world_owner_matches_world",
        ),
        Index(
            "ix_image_revisions_owner_history",
            "world_id",
            "owner_kind",
            "owner_id",
            "created_at",
        ),
    )

    world_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("worlds.id", ondelete="CASCADE"), nullable=False
    )
    owner_kind: Mapped[ImageOwnerKind] = mapped_column(
        SAEnum(ImageOwnerKind, name="image_owner_kind"), nullable=False
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    file_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("files.id", ondelete="CASCADE"), nullable=False
    )
    file: Mapped[FileModel] = relationship(lazy="joined")
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    uploaded_by: Mapped[UserModel | None] = relationship(lazy="joined")
