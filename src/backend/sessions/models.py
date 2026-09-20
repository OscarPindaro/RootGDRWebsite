import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..content.models import ContentDocumentMixin, TintedMixin
from ..db.db import Base
from ..db.mixins import TimestampMixin, UUIDv7PrimaryKeyMixin
from ..users.models import UserModel


class SessionModel(
    Base,
    UUIDv7PrimaryKeyMixin,
    TimestampMixin,
    ContentDocumentMixin,
    TintedMixin,
):
    __tablename__ = "sessions"

    world_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("worlds.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    created_by: Mapped[UserModel] = relationship(lazy="select")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    in_world_date: Mapped[str] = mapped_column(String(255), nullable=False)
    real_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    short_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
