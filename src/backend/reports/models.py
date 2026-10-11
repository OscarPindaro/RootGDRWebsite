"""In-app bug reports and the captures attached to them.

A report starts as a draft: what the reader wrote plus the screenshots and page
HTML the panel uploaded. It becomes a board ticket only on submission, so the
draft is a row here and nothing more. The id is a random UUID because the
browser keeps it as its only handle on the draft, and an unguessable id is the
whole access control for a visitor who is not signed in.
"""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.db import Base
from ..db.mixins import TimestampMixin, UUIDv4PrimaryKeyMixin, UUIDv7PrimaryKeyMixin
from ..users.models import UserModel


class ReportState(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"


class EvidenceKind(str, Enum):
    """One capture per kind; uploading again replaces that row's file."""

    SCREENSHOT_VIEWPORT = "screenshot_viewport"
    SCREENSHOT_FULL_PAGE = "screenshot_full_page"
    PAGE_HTML = "page_html"


class ReportModel(Base, UUIDv4PrimaryKeyMixin, TimestampMixin):
    """One report, draft until it is submitted."""

    __tablename__ = "reports"

    state: Mapped[ReportState] = mapped_column(
        SAEnum(ReportState, name="report_state"),
        nullable=False,
        default=ReportState.DRAFT,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    page_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    user_agent: Mapped[str] = mapped_column(Text, nullable=False, default="")
    viewport_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    viewport_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reporter_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # The reproduction: one browser session and one backend session, both scoped
    # to this report. The browser is joined to them by a cookie, so ordinary
    # navigation keeps recording without the reader copying an id.
    frontend_session: Mapped[str | None] = mapped_column(String(64), nullable=True)
    backend_session: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reproduction_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reproduction_stopped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reporter: Mapped[UserModel | None] = relationship(lazy="joined")
    evidence: Mapped[list["ReportEvidenceModel"]] = relationship(
        back_populates="report",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ReportEvidenceModel.kind",
    )


class ReportEvidenceModel(Base, UUIDv7PrimaryKeyMixin, TimestampMixin):
    """One stored capture: a screenshot or the rendered page HTML.

    The file's own metadata lives here rather than in ``files``: a capture
    belongs to exactly one report and is never shared, so the extra join would
    only add indirection.
    """

    __tablename__ = "report_evidence"
    __table_args__ = (
        UniqueConstraint("report_id", "kind", name="uq_report_evidence_report_kind"),
    )

    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    report: Mapped[ReportModel] = relationship(back_populates="evidence")
    kind: Mapped[EvidenceKind] = mapped_column(
        SAEnum(EvidenceKind, name="report_evidence_kind"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(127), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
