from typing import Annotated

from pydantic import Field

from ..schemas import AppBaseModel, TimestampMixin, UUIDField
from ..users.schemas import UserResponse


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
            description="World description",
        ),
    ]
    shared_with: Annotated[
        list[UUIDField],
        Field(
            default_factory=list,
            description="User IDs allowed to view this private world",
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
    shared_with: Annotated[
        list[UUIDField] | None,
        Field(default=None, description="Replacement list of users allowed to view"),
    ]


class WorldResponse(AppBaseModel, TimestampMixin):
    id: Annotated[UUIDField, Field(description="World ID")]
    name: Annotated[str, Field(max_length=255, description="World name")]
    description: Annotated[
        str, Field(max_length=10_000, description="World description")
    ]
    created_by: Annotated[UserResponse, Field(description="User who created the world")]
    shared_with: Annotated[
        list[UserResponse] | None,
        Field(
            default=None, description="Users allowed to view the world, when requested"
        ),
    ]
