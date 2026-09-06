from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path

from acp.schema import PermissionOption
from pydantic import BaseModel, ConfigDict, Field


class Verbosity(StrEnum):
    QUIET = "quiet"
    STATUS = "status"
    VERBOSE = "verbose"
    TRACE = "trace"


class PermissionPolicy(StrEnum):
    BALANCED = "balanced"
    BYPASS = "bypass"


class SessionState(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    REQUIRES_ACTION = "requires_action"
    INTERRUPTED = "interrupted"
    CLOSED = "closed"


class QueueState(StrEnum):
    QUEUED = "queued"
    DISPATCHING = "dispatching"
    ACCEPTED = "accepted"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


class DomainModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProjectRecord(DomainModel):
    id: int
    name: str
    root_path: Path
    enabled: bool


class UserPreferencesRecord(DomainModel):
    telegram_user_id: int
    default_project_id: int
    active_session_id: int | None
    default_verbosity: Verbosity
    default_policy: PermissionPolicy


class SessionRecord(DomainModel):
    id: int
    acp_session_id: str
    project_id: int
    telegram_user_id: int
    title: str | None
    state: SessionState
    verbosity: Verbosity
    policy: PermissionPolicy
    created_at: datetime
    updated_at: datetime


class AttachmentManifestItem(BaseModel):
    path: Path
    mime_type: str
    size: int


class AttachmentManifest(BaseModel):
    items: list[AttachmentManifestItem] = Field(default_factory=list)


class PermissionOptions(BaseModel):
    items: list[PermissionOption] = Field(default_factory=list)


class PromptRecord(DomainModel):
    id: int
    session_id: int
    prompt_text: str
    attachment_manifest: AttachmentManifest
    priority: int
    state: QueueState
    created_at: datetime
    dispatched_at: datetime | None


class PendingPermissionRecord(DomainModel):
    id: str
    session_id: int
    tool_call_id: str
    options: PermissionOptions
    state: str
    telegram_message_id: int | None
    created_at: datetime
    resolved_at: datetime | None
