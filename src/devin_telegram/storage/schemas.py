from __future__ import annotations

from pathlib import Path

from acp.schema import PermissionOption
from pydantic import BaseModel, Field

from ..domain import (
    AttachmentManifest,
    PermissionPolicy,
    QueueState,
    SessionState,
    Verbosity,
)


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    root_path: Path


class UserPreferencesCreate(BaseModel):
    telegram_user_id: int
    default_project_id: int
    default_verbosity: Verbosity = Verbosity.STATUS
    default_policy: PermissionPolicy = PermissionPolicy.BALANCED


class SessionCreate(BaseModel):
    acp_session_id: str
    project_id: int
    telegram_user_id: int
    state: SessionState = SessionState.IDLE
    verbosity: Verbosity
    policy: PermissionPolicy


class PromptCreate(BaseModel):
    session_id: int
    prompt_text: str = Field(min_length=1)
    attachment_manifest: AttachmentManifest = Field(default_factory=AttachmentManifest)
    priority: int = 0
    state: QueueState = QueueState.QUEUED


class PendingPermissionCreate(BaseModel):
    id: str
    session_id: int
    tool_call_id: str
    options: list[PermissionOption]
