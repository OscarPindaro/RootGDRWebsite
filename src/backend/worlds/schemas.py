from datetime import datetime
from typing import Annotated

from pydantic import Field

from ..db.enums import WorldRole
from ..schemas import AppBaseModel, TimestampMixin, UUIDField
from ..users.schemas import UserResponse


class WorldMemberInput(AppBaseModel):
    user_id: Annotated[UUIDField, Field(description="User ID of the member")]
    role: Annotated[
        WorldRole,
        Field(default=WorldRole.PLAYER, description="Role inside the world"),
    ]


class WorldCreate(AppBaseModel):
    name: Annotated[
        str,
        Field(
            min_length=1,
            max_length=255,
            examples=["The Shattered Coast"],
            description="World name",
        ),
    ]
    description: Annotated[
        str,
        Field(
            min_length=1,
            max_length=10_000,
            examples=["An archipelago recovering from a century-old magical storm."],
            description="World description (Markdown)",
        ),
    ]
    members: Annotated[
        list[WorldMemberInput],
        Field(
            default_factory=list,
            description="Additional members. The creator is always a master.",
        ),
    ]


class WorldUpdate(AppBaseModel):
    name: Annotated[
        str | None,
        Field(
            default=None,
            min_length=1,
            max_length=255,
            description="Replacement world name",
        ),
    ]
    description: Annotated[
        str | None,
        Field(
            default=None,
            min_length=1,
            max_length=10_000,
            description="Replacement world description",
        ),
    ]
    members: Annotated[
        list[WorldMemberInput] | None,
        Field(
            default=None,
            description="Replacement member list. The owner cannot be removed.",
        ),
    ]


class WorldMemberResponse(AppBaseModel):
    user: Annotated[UserResponse, Field(description="The member")]
    role: Annotated[WorldRole, Field(description="Role inside the world")]


class WorldResponse(AppBaseModel, TimestampMixin):
    id: Annotated[UUIDField, Field(description="World ID")]
    name: Annotated[str, Field(max_length=255, description="World name")]
    description: Annotated[
        str, Field(max_length=10_000, description="World description (Markdown)")
    ]
    image_url: Annotated[
        str | None, Field(default=None, description="Authenticated world image URL")
    ]
    created_by: Annotated[UserResponse, Field(description="User who created the world")]
    members: Annotated[
        list[WorldMemberResponse] | None,
        Field(default=None, description="World members, when requested"),
    ]


class WorldSummary(AppBaseModel):
    """A world as shown on a cover card."""

    id: Annotated[UUIDField, Field(description="World ID")]
    name: Annotated[str, Field(description="World name")]
    description: Annotated[str, Field(description="Short description")]
    image_url: Annotated[str | None, Field(default=None)]
    role: Annotated[WorldRole, Field(description="The viewer's role in the world")]
    volume: Annotated[int, Field(description="Position in the viewer's list")]
    updated_at: Annotated[datetime, Field(description="Last update timestamp")]
