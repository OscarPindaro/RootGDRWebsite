"""Mutation rules shared by content documents."""

from typing import Annotated, Protocol

from fastapi import HTTPException, status
from pydantic import Field

from ..concurrency import VersionedUpdate, require_expected_version


class ContentDocument(Protocol):
    version: int
    locked: bool
    is_draft: bool


class ContentUpdate(VersionedUpdate):
    locked: Annotated[bool | None, Field(default=None)]
    is_draft: Annotated[bool | None, Field(default=None)]


class ContentLockedException(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_423_LOCKED,
            detail="Unlock the document before editing it",
        )


def require_draft(document: ContentDocument) -> None:
    if not document.is_draft:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only drafts can be cancelled",
        )


def require_content_update(document: ContentDocument, data: ContentUpdate) -> None:
    """Check the version and permit only a standalone unlock while locked."""
    require_expected_version(document, data.expected_version)
    if document.locked and not (
        data.locked is False and data.model_fields_set <= {"locked", "expected_version"}
    ):
        raise ContentLockedException()
