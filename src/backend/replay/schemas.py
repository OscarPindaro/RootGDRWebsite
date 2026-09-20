"""Recorded user actions, replayed as a generated test."""

from typing import Annotated, Literal

from pydantic import Field

from ..schemas import AppBaseModelStripped

StepKind = Literal["goto", "fill", "select", "click"]


class ReplayStep(AppBaseModelStripped):
    """One thing the user did, described semantically rather than as a raw event."""

    kind: StepKind
    url: Annotated[str | None, Field(default=None, description="For goto steps")]
    selector: Annotated[str | None, Field(default=None, description="CSS selector")]
    value: Annotated[str | None, Field(default=None, description="Field value")]
    label: Annotated[str | None, Field(default=None, description="Human-readable note")]


class ReplayBatch(AppBaseModelStripped):
    session: Annotated[str, Field(min_length=1, max_length=64)]
    steps: Annotated[list[ReplayStep], Field(default_factory=list)]


class BackendStep(AppBaseModelStripped):
    """One request the backend answered, recorded for a replay test."""

    method: str
    path: str
    query: Annotated[str | None, Field(default=None, description="Raw query string")]
    body: Annotated[object | None, Field(default=None, description="JSON request body")]
    status: Annotated[int, Field(description="Response status")]
