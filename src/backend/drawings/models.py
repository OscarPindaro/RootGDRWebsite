import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from ..db.db import Base
from ..db.mixins import OptimisticLockMixin, TimestampMixin, UUIDv7PrimaryKeyMixin
from ..users.models import UserModel
from .schemas import SceneDocument


class SceneJSON(TypeDecorator[SceneDocument]):
    impl = JSONB
    cache_ok = True

    def process_bind_param(self, value: SceneDocument, dialect):
        return SceneDocument.model_validate(value).model_dump(mode="json")

    def process_result_value(self, value, dialect) -> SceneDocument:
        return SceneDocument.model_validate(value)


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
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[UserModel | None] = relationship(lazy="joined")
    document: Mapped[SceneDocument] = mapped_column(SceneJSON, nullable=False)
