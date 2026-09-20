"""Schemas must treat a blank form field as absent.

htmx's json-enc serialises every control, so an optional field left empty
arrives as ``""``. Before these guards, creating a session without a real date,
or a page without a slug or menu position, failed with a 422.
"""

from __future__ import annotations

from datetime import date

from src.backend.pages.schemas import PageCreate, PageUpdate
from src.backend.sessions.schemas import SessionCreate


def test_session_real_date_accepts_a_blank_value() -> None:
    assert SessionCreate(title="x", in_world_date="y", real_date="").real_date is None
    assert SessionCreate(
        title="x", in_world_date="y", real_date="2024-01-02"
    ).real_date == date(2024, 1, 2)


def test_page_create_accepts_a_blank_slug_and_menu_position() -> None:
    page = PageCreate(title="Le regole della Casa", slug="", menu_position="")

    assert page.slug is None
    assert page.menu_position == 0


def test_page_update_accepts_a_blank_menu_position() -> None:
    assert PageUpdate(menu_position="").menu_position is None
