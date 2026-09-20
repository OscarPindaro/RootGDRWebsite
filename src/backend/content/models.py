"""Shared column mixins for content documents.

Characters, NPCs, places, sessions, stories and pages all carry a Markdown body
and the locked / draft states, so those columns are declared once.
"""

import uuid

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..db.db import Base
from ..db.mixins import TimestampMixin, UUIDv7PrimaryKeyMixin
from .constants import DEFAULT_TINT


class ContentDocumentMixin:
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_draft: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class TintedMixin:
    tint: Mapped[str] = mapped_column(String(8), nullable=False, default=DEFAULT_TINT)


class ReferenceModel(Base, UUIDv7PrimaryKeyMixin, TimestampMixin):
    """One `@[label]` occurrence, resolved when its source is saved.

    ``target_kind``/``target_id`` are null when the label matches nothing
    (missing) or more than one item (ambiguous). Backlinks are an indexed lookup
    on the target columns rather than a re-scan of every body.
    """

    __tablename__ = "references"
    __table_args__ = (
        UniqueConstraint("source_kind", "source_id", "label", name="uq_reference"),
        Index("ix_reference_source", "source_kind", "source_id"),
        Index("ix_reference_target", "target_kind", "target_id"),
    )

    world_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("worlds.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    target_kind: Mapped[str | None] = mapped_column(String(16), nullable=True)
    target_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
