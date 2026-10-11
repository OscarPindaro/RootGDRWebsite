import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.db import Base
from ..db.mixins import OptimisticLockMixin, TimestampMixin, UUIDv7PrimaryKeyMixin
from ..users.models import UserModel


class DrawingModel(
    Base,
    UUIDv7PrimaryKeyMixin,
    TimestampMixin,
    OptimisticLockMixin,
):
    """One editable geometric scene.

    The native document is the JSONB column: geometry, hierarchy and styles in
    the drawing feature's own typed format, never flattened SVG. ``version`` is
    the optimistic lock and is unrelated to the document's own
    ``schema_version``.
    """

    __tablename__ = "drawings"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[UserModel | None] = relationship(lazy="joined")
    document: Mapped[dict] = mapped_column(JSONB, nullable=False)
