"""Shared optimistic-concurrency API contract."""

from typing import Annotated, Protocol

from fastapi import HTTPException, status
from pydantic import BaseModel, Field

from .schemas import AppBaseModel


class Versioned(Protocol):
    version: int


class VersionedUpdate(AppBaseModel):
    """Client version used as a precondition, never as an assigned model field."""

    expected_version: Annotated[int | None, Field(default=None, ge=1)]


class VersionedResponse(BaseModel):
    version: Annotated[int, Field(ge=1, description="Optimistic lock version")]


class VersionConflictException(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail="The document changed since it was read",
        )


def require_expected_version(document: Versioned, expected_version: int | None) -> None:
    if expected_version is not None and document.version != expected_version:
        raise VersionConflictException()
