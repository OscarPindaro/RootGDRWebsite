from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from ..domain import (
    AttachmentManifest,
    PermissionOptions,
    PermissionPolicy,
    QueueState,
    SessionState,
    Verbosity,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def enum_column(enum_type: type) -> SAEnum:
    return SAEnum(
        enum_type,
        values_callable=lambda members: [member.value for member in members],
        native_enum=False,
    )


class PydanticType(TypeDecorator[str]):
    impl = Text
    cache_ok = True

    def __init__(self, model_type: type[BaseModel]) -> None:
        super().__init__()
        self.model_type = model_type

    def process_bind_param(self, value: BaseModel | None, dialect: Any) -> str | None:
        return value.model_dump_json() if value is not None else None

    def process_result_value(self, value: str | None, dialect: Any) -> BaseModel | None:
        return self.model_type.model_validate_json(value) if value is not None else None


class Base(DeclarativeBase):
    pass


class ProjectModel(Base):
    __tablename__ = "devin_telegram_projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    root_path: Mapped[str] = mapped_column(String(2048), unique=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class SessionModel(Base):
    __tablename__ = "devin_telegram_sessions"
    __table_args__ = (
        UniqueConstraint("acp_session_id", name="uq_devin_telegram_session_acp"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    acp_session_id: Mapped[str] = mapped_column(String(255), nullable=False)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("devin_telegram_projects.id"), nullable=False, index=True
    )
    telegram_user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(500))
    state: Mapped[SessionState] = mapped_column(
        enum_column(SessionState), nullable=False
    )
    verbosity: Mapped[Verbosity] = mapped_column(enum_column(Verbosity), nullable=False)
    policy: Mapped[PermissionPolicy] = mapped_column(
        enum_column(PermissionPolicy), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class UserPreferencesModel(Base):
    __tablename__ = "devin_telegram_user_preferences"

    telegram_user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    default_project_id: Mapped[int] = mapped_column(
        ForeignKey("devin_telegram_projects.id"), nullable=False
    )
    active_session_id: Mapped[int | None] = mapped_column(
        ForeignKey("devin_telegram_sessions.id")
    )
    default_verbosity: Mapped[Verbosity] = mapped_column(
        enum_column(Verbosity), nullable=False
    )
    default_policy: Mapped[PermissionPolicy] = mapped_column(
        enum_column(PermissionPolicy), nullable=False
    )


class PromptModel(Base):
    __tablename__ = "devin_telegram_prompt_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("devin_telegram_sessions.id"), nullable=False, index=True
    )
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    attachment_manifest: Mapped[AttachmentManifest] = mapped_column(
        PydanticType(AttachmentManifest),
        default=AttachmentManifest,
        nullable=False,
    )
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    state: Mapped[QueueState] = mapped_column(enum_column(QueueState), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PendingPermissionModel(Base):
    __tablename__ = "devin_telegram_pending_permissions"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("devin_telegram_sessions.id"), nullable=False, index=True
    )
    tool_call_id: Mapped[str] = mapped_column(String(255), nullable=False)
    options: Mapped[PermissionOptions] = mapped_column(
        PydanticType(PermissionOptions), nullable=False
    )
    state: Mapped[str] = mapped_column(String(100), default="pending", nullable=False)
    telegram_message_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
