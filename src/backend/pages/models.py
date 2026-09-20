import uuid

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..content.models import ContentDocumentMixin, TintedMixin
from ..db.db import Base
from ..db.mixins import OptimisticLockMixin, TimestampMixin, UUIDv7PrimaryKeyMixin
from ..users.models import UserModel


class PageModel(
    Base,
    UUIDv7PrimaryKeyMixin,
    TimestampMixin,
    OptimisticLockMixin,
    ContentDocumentMixin,
    TintedMixin,
):
    __tablename__ = "pages"
    __table_args__ = (UniqueConstraint("world_id", "slug", name="uq_page_world_slug"),)

    world_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("worlds.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    created_by: Mapped[UserModel] = relationship(lazy="select")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    short_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    menu_position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
