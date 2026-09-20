"""Shared column mixins for content documents.

Characters, NPCs, places, sessions, stories and pages all carry a Markdown body
and the locked / draft states, so those columns are declared once.
"""

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .constants import DEFAULT_TINT


class ContentDocumentMixin:
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_draft: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class TintedMixin:
    tint: Mapped[str] = mapped_column(String(8), nullable=False, default=DEFAULT_TINT)
