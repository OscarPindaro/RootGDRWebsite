import uuid
from enum import Enum

from sqlalchemy import Column, Enum as SAEnum, ForeignKey, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..content.models import ContentDocumentMixin, TintedMixin
from ..db.db import Base
from ..db.mixins import TimestampMixin, UUIDv7PrimaryKeyMixin
from ..sessions.models import SessionModel
from ..users.models import UserModel


class StoryStatus(str, Enum):
    """Whether a story arc is still running."""

    OPEN = "in_corso"
    CLOSED = "chiusa"


story_sessions = Table(
    "story_sessions",
    Base.metadata,
    Column("story_id", ForeignKey("stories.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "session_id",
        ForeignKey("sessions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class StoryModel(
    Base,
    UUIDv7PrimaryKeyMixin,
    TimestampMixin,
    ContentDocumentMixin,
    TintedMixin,
):
    __tablename__ = "stories"

    world_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("worlds.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    created_by: Mapped[UserModel] = relationship(lazy="select")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    short_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    period_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[StoryStatus] = mapped_column(
        SAEnum(StoryStatus, name="story_status"),
        nullable=False,
        default=StoryStatus.OPEN,
    )
    sessions: Mapped[list[SessionModel]] = relationship(
        secondary=story_sessions, lazy="select"
    )
