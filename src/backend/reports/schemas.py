"""Transport schemas for the report panel."""

from typing import Annotated

from pydantic import Field

from ..schemas import AppBaseModel, TimestampMixin, UUIDField
from .models import EvidenceKind, ReportState

MAX_DESCRIPTION = 20_000
MAX_PAGE_URL = 2_048
MAX_USER_AGENT = 1_024
MAX_SCREENSHOT_BYTES = 5 * 1024 * 1024
MAX_PAGE_HTML_BYTES = 2 * 1024 * 1024


class ReportCreate(AppBaseModel):
    """What the panel knows before the reader has written anything."""

    page_url: Annotated[str, Field(max_length=MAX_PAGE_URL)] = ""
    viewport_width: Annotated[int | None, Field(default=None, ge=1, le=20_000)] = None
    viewport_height: Annotated[int | None, Field(default=None, ge=1, le=20_000)] = None


class ReportUpdate(AppBaseModel):
    description: Annotated[str, Field(max_length=MAX_DESCRIPTION)]


class ReportEvidenceResponse(AppBaseModel, TimestampMixin):
    kind: Annotated[EvidenceKind, Field(description="Capture kind")]
    filename: Annotated[str, Field(description="Original file name")]
    content_type: Annotated[str, Field(description="Media type")]
    byte_size: Annotated[int, Field(description="Stored size in bytes")]
    sha256: Annotated[str, Field(description="Stored content digest")]


class ReportResponse(AppBaseModel, TimestampMixin):
    id: Annotated[UUIDField, Field(description="Report ID")]
    state: Annotated[ReportState, Field(description="Draft or submitted")]
    description: str = ""
    page_url: str = ""
    user_agent: str = ""
    viewport_width: int | None = None
    viewport_height: int | None = None
    evidence: list[ReportEvidenceResponse] = Field(default_factory=list)
