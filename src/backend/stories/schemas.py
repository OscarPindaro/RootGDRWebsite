from typing import Annotated

from pydantic import Field

from ..concurrency import VersionedResponse
from ..content.constants import DEFAULT_TINT, Tint
from ..content.policy import ContentUpdate
from ..schemas import AppBaseModel, TimestampMixin, UUIDField
from ..users.schemas import UserResponse
from .models import StoryStatus


class StoryCreate(AppBaseModel):
    title: Annotated[str, Field(min_length=1, max_length=255)]
    short_description: Annotated[str, Field(default="", max_length=1000)]
    period_label: Annotated[str | None, Field(default=None, max_length=255)]
    status: Annotated[StoryStatus, Field(default=StoryStatus.OPEN)]
    tint: Annotated[Tint, Field(default=DEFAULT_TINT)]
    body: Annotated[str, Field(default="", max_length=100_000)]
    session_ids: Annotated[list[UUIDField], Field(default_factory=list)]
    is_draft: Annotated[bool, Field(default=False)]


class StoryUpdate(ContentUpdate):
    title: Annotated[str | None, Field(default=None, min_length=1, max_length=255)]
    short_description: Annotated[str | None, Field(default=None, max_length=1000)]
    period_label: Annotated[str | None, Field(default=None, max_length=255)]
    status: Annotated[StoryStatus | None, Field(default=None)]
    tint: Annotated[Tint | None, Field(default=None)]
    body: Annotated[str | None, Field(default=None, max_length=100_000)]
    session_ids: Annotated[list[UUIDField] | None, Field(default=None)]


class StorySummary(AppBaseModel, TimestampMixin, VersionedResponse):
    id: Annotated[UUIDField, Field(description="Story ID")]
    title: Annotated[str, Field(description="Title")]
    short_description: Annotated[str, Field(default="")]
    period_label: Annotated[str | None, Field(default=None)]
    status: Annotated[StoryStatus, Field(default=StoryStatus.OPEN)]
    tint: Annotated[Tint, Field(default=DEFAULT_TINT)]
    locked: Annotated[bool, Field(default=False)]
    is_draft: Annotated[bool, Field(default=False)]


class StoryResponse(StorySummary):
    body: Annotated[str, Field(default="")]
    created_by: Annotated[UserResponse, Field(description="Master who wrote it")]
