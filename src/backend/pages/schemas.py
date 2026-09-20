import re
from typing import Annotated

from pydantic import Field, field_validator

from ..content.constants import DEFAULT_TINT, Tint
from ..schemas import AppBaseModel, TimestampMixin, UUIDField
from ..users.schemas import UserResponse

_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def slugify(value: str) -> str:
    """Lowercase, accent-folded, hyphenated slug."""
    folded = (
        value.lower()
        .replace("à", "a")
        .replace("è", "e")
        .replace("é", "e")
        .replace("ì", "i")
        .replace("ò", "o")
        .replace("ù", "u")
        .replace("'", " ")
    )
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", folded)).strip("-")


class PageCreate(AppBaseModel):
    title: Annotated[str, Field(min_length=1, max_length=255)]
    slug: Annotated[str | None, Field(default=None, max_length=255)]
    short_description: Annotated[str, Field(default="", max_length=1000)]
    menu_position: Annotated[int, Field(default=0, ge=0)]
    tint: Annotated[Tint, Field(default=DEFAULT_TINT)]
    body: Annotated[str, Field(default="", max_length=100_000)]
    is_draft: Annotated[bool, Field(default=False)]

    @field_validator("slug")
    @classmethod
    def _slug(cls, value: str | None) -> str | None:
        if not value:
            return None
        value = slugify(value)
        if not value or not _SLUG.match(value):
            raise ValueError("Slug must contain letters, digits and hyphens")
        return value

    @field_validator("menu_position", mode="before")
    @classmethod
    def _empty_position(cls, value: object) -> object:
        return 0 if value == "" else value


class PageUpdate(AppBaseModel):
    title: Annotated[str | None, Field(default=None, min_length=1, max_length=255)]
    slug: Annotated[str | None, Field(default=None, max_length=255)]
    short_description: Annotated[str | None, Field(default=None, max_length=1000)]
    menu_position: Annotated[int | None, Field(default=None, ge=0)]
    tint: Annotated[Tint | None, Field(default=None)]
    body: Annotated[str | None, Field(default=None, max_length=100_000)]
    locked: Annotated[bool | None, Field(default=None)]
    is_draft: Annotated[bool | None, Field(default=None)]

    @field_validator("slug")
    @classmethod
    def _slug(cls, value: str | None) -> str | None:
        return PageCreate._slug(value)

    @field_validator("menu_position", mode="before")
    @classmethod
    def _empty_position(cls, value: object) -> object:
        return None if value == "" else value


class PageSummary(AppBaseModel, TimestampMixin):
    id: Annotated[UUIDField, Field(description="Page ID")]
    title: Annotated[str, Field(description="Title")]
    slug: Annotated[str, Field(description="URL slug, unique within the world")]
    short_description: Annotated[str, Field(default="")]
    menu_position: Annotated[int, Field(default=0)]
    tint: Annotated[Tint, Field(default=DEFAULT_TINT)]
    locked: Annotated[bool, Field(default=False)]
    is_draft: Annotated[bool, Field(default=False)]


class PageResponse(PageSummary):
    body: Annotated[str, Field(default="")]
    created_by: Annotated[UserResponse, Field(description="Master who wrote it")]
