from typing import Annotated

from pydantic import Field, field_validator

from ..concurrency import VersionedResponse
from ..content.constants import ANIMALS, DEFAULT_ANIMAL, DEFAULT_TINT, Tint
from ..content.policy import ContentUpdate
from ..schemas import AppBaseModel, TimestampMixin, UUIDField
from ..users.schemas import UserResponse


class CharacterCreate(AppBaseModel):
    name: Annotated[str, Field(min_length=1, max_length=255)]
    title: Annotated[str | None, Field(default=None, max_length=255)]
    short_description: Annotated[str, Field(default="", max_length=1000)]
    body: Annotated[str, Field(default="", max_length=100_000)]
    tint: Annotated[Tint, Field(default=DEFAULT_TINT)]
    animal: Annotated[str, Field(default=DEFAULT_ANIMAL)]
    is_draft: Annotated[bool, Field(default=False)]
    owner_id: Annotated[UUIDField | None, Field(default=None)]

    @field_validator("animal")
    @classmethod
    def _known_animal(cls, value: str) -> str:
        if value not in ANIMALS:
            raise ValueError("Unknown animal")
        return value


class CharacterUpdate(ContentUpdate):
    name: Annotated[str | None, Field(default=None, min_length=1, max_length=255)]
    title: Annotated[str | None, Field(default=None, max_length=255)]
    short_description: Annotated[str | None, Field(default=None, max_length=1000)]
    body: Annotated[str | None, Field(default=None, max_length=100_000)]
    tint: Annotated[Tint | None, Field(default=None)]
    animal: Annotated[str | None, Field(default=None)]

    @field_validator("animal")
    @classmethod
    def _known_animal(cls, value: str | None) -> str | None:
        if value is not None and value not in ANIMALS:
            raise ValueError("Unknown animal")
        return value


class CharacterSummary(AppBaseModel, TimestampMixin, VersionedResponse):
    id: Annotated[UUIDField, Field(description="Character ID")]
    name: Annotated[str, Field(description="Full name")]
    title: Annotated[str | None, Field(default=None)]
    short_description: Annotated[str, Field(default="")]
    tint: Annotated[Tint, Field(default=DEFAULT_TINT)]
    animal: Annotated[str, Field(default=DEFAULT_ANIMAL)]
    image_url: Annotated[str | None, Field(default=None)]
    owner: Annotated[UserResponse, Field(description="Owning user")]
    locked: Annotated[bool, Field(default=False)]
    is_draft: Annotated[bool, Field(default=False)]


class CharacterResponse(CharacterSummary):
    body: Annotated[str, Field(default="")]
