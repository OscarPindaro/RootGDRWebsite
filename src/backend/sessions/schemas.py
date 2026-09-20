from datetime import date
from typing import Annotated

from pydantic import Field

from ..content.constants import DEFAULT_TINT, Tint
from ..schemas import AppBaseModel, OptionalDate, TimestampMixin, UUIDField
from ..users.schemas import UserResponse


class SessionCreate(AppBaseModel):
    title: Annotated[str, Field(min_length=1, max_length=255)]
    in_world_date: Annotated[str, Field(min_length=1, max_length=255)]
    real_date: OptionalDate = None
    short_description: Annotated[str, Field(default="", max_length=1000)]
    body: Annotated[str, Field(default="", max_length=100_000)]
    tint: Annotated[Tint, Field(default=DEFAULT_TINT)]
    is_draft: Annotated[bool, Field(default=False)]


class SessionUpdate(AppBaseModel):
    title: Annotated[str | None, Field(default=None, min_length=1, max_length=255)]
    in_world_date: Annotated[
        str | None, Field(default=None, min_length=1, max_length=255)
    ]
    real_date: OptionalDate = None
    short_description: Annotated[str | None, Field(default=None, max_length=1000)]
    body: Annotated[str | None, Field(default=None, max_length=100_000)]
    tint: Annotated[Tint | None, Field(default=None)]
    locked: Annotated[bool | None, Field(default=None)]
    is_draft: Annotated[bool | None, Field(default=None)]


class SessionSummary(AppBaseModel, TimestampMixin):
    id: Annotated[UUIDField, Field(description="Session ID")]
    title: Annotated[str, Field(description="Title")]
    in_world_date: Annotated[str, Field(description="In-world date label")]
    real_date: Annotated[date | None, Field(default=None)]
    short_description: Annotated[str, Field(default="")]
    tint: Annotated[Tint, Field(default=DEFAULT_TINT)]
    number: Annotated[int, Field(default=0, description="Position in the ledger")]
    locked: Annotated[bool, Field(default=False)]
    is_draft: Annotated[bool, Field(default=False)]


class SessionResponse(SessionSummary):
    body: Annotated[str, Field(default="")]
    created_by: Annotated[UserResponse, Field(description="Master who wrote it")]
