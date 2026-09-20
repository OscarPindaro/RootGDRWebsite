from typing import Annotated

from pydantic import Field, field_validator

from ..concurrency import VersionedResponse
from ..content.constants import DEFAULT_SHAPE, DEFAULT_TINT, SHAPE_NAMES, Shape, Tint
from ..content.policy import ContentUpdate
from ..schemas import AppBaseModel, TimestampMixin, UUIDField
from ..users.schemas import UserResponse


def _known_shape(value: str) -> str:
    if value not in SHAPE_NAMES:
        raise ValueError("Unknown shape")
    return value


class PlaceCreate(AppBaseModel):
    name: Annotated[str, Field(min_length=1, max_length=255)]
    short_description: Annotated[str, Field(default="", max_length=1000)]
    body: Annotated[str, Field(default="", max_length=100_000)]
    tint: Annotated[Tint, Field(default=DEFAULT_TINT)]
    shape: Annotated[Shape, Field(default=DEFAULT_SHAPE)]
    is_draft: Annotated[bool, Field(default=False)]

    @field_validator("shape")
    @classmethod
    def _shape(cls, value: str) -> str:
        return _known_shape(value)


class PlaceUpdate(ContentUpdate):
    name: Annotated[str | None, Field(default=None, min_length=1, max_length=255)]
    short_description: Annotated[str | None, Field(default=None, max_length=1000)]
    body: Annotated[str | None, Field(default=None, max_length=100_000)]
    tint: Annotated[Tint | None, Field(default=None)]
    shape: Annotated[str | None, Field(default=None)]

    @field_validator("shape")
    @classmethod
    def _shape(cls, value: str | None) -> str | None:
        return _known_shape(value) if value is not None else None


class PlaceSummary(AppBaseModel, TimestampMixin, VersionedResponse):
    id: Annotated[UUIDField, Field(description="Place ID")]
    name: Annotated[str, Field(description="Name")]
    short_description: Annotated[str, Field(default="")]
    tint: Annotated[Tint, Field(default=DEFAULT_TINT)]
    shape: Annotated[Shape, Field(default=DEFAULT_SHAPE)]
    image_url: Annotated[str | None, Field(default=None)]
    locked: Annotated[bool, Field(default=False)]
    is_draft: Annotated[bool, Field(default=False)]


class PlaceResponse(PlaceSummary):
    body: Annotated[str, Field(default="")]
    created_by: Annotated[UserResponse, Field(description="Master who wrote it")]
