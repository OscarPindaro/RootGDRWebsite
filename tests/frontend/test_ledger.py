"""Component tests for ``editorial.Ledger`` and ``editorial.LedgerRow``.

Sessions and pages are ledgers: a fixed column grid that reads as records, not
as a card grid. F14 extracted the shell and the row so both pages share one
structure, and moved the phone fold with it. The ledger must not turn into
cards, and the session ledger keeps its tint dot and its tag column.
"""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.navigation import Crumb, WorldContext

pytestmark = pytest.mark.frontend

WORLD_ID = "11111111-1111-1111-1111-111111111111"


def _user() -> SimpleNamespace:
    return SimpleNamespace(
        name="Ada",
        email="ada@example.com",
        role="admin",
        avatar_url=None,
        symbol_style="icons",
    )


def _world() -> SimpleNamespace:
    return SimpleNamespace(
        id=WORLD_ID,
        name="Il Boschetto di Smeraldo",
        description="d",
        version=1,
        image_url=None,
        current_place_id=None,
    )


def _session(number: int = 1) -> tuple[int, SimpleNamespace]:
    return (
        number,
        SimpleNamespace(
            id=uuid4(),
            in_world_date="12 marzo",
            real_date=None,
            title="Il risveglio della Marchesa",
            short_description="La compagnia torna al Boschetto.",
            is_draft=False,
            tint="cobalt",
        ),
    )


def _session_page(component, rows):
    world = _world()
    return component.mount(
        "pages.sessions.SessionList",
        props={
            "world": world,
            "world_context": WorldContext(id=WORLD_ID, name=world.name, role="Master"),
            "nav": None,
            "rows": rows,
            "crumbs": [Crumb(label="Mondi", href="/worlds"), Crumb(label=world.name)],
            "pages": [],
            "drafts": None,
            "can_manage": True,
            "current_user": _user(),
        },
    )


def _row(component, **overrides):
    props = dict(
        href="#",
        title="Sessione",
        summary="d",
        number="01",
        meta="12 marzo",
        tag="Bozza",
        tint="cobalt",
    )
    props.update(overrides)
    return component.mount("editorial.LedgerRow", props=props)


def test_the_session_page_is_a_ledger_not_a_card_grid(component):
    page = _session_page(component, [_session()])

    assert page.locator(".ledger").count() == 1
    assert page.locator(".ledger__row").count() == 1
    assert page.locator(".entity-card").count() == 0
    assert page.locator(".ledger__head .eyebrow").count() == 4
    # A published session has no tag, so the tag cell must not render "None".
    assert "None" not in page.locator(".ledger__row").inner_text()
    assert page.locator(".ledger__tag").count() == 0


def test_the_session_row_keeps_its_four_columns(component):
    page = _session_page(component, [_session()])

    columns = page.locator(".ledger__row").evaluate(
        "el => getComputedStyle(el).gridTemplateColumns"
    )
    assert len(columns.split()) == 4


def test_the_number_carries_the_session_tint_dot(component):
    page = _session_page(component, [_session()])

    assert page.locator(".ledger__num .sdot").count() == 1


def test_the_ledger_folds_to_two_columns_on_a_phone(component):
    page = _session_page(component, [_session()])
    page.set_viewport_size({"width": 390, "height": 844})

    columns = page.locator(".ledger__row").evaluate(
        "el => getComputedStyle(el).gridTemplateColumns"
    )
    assert len(columns.split()) == 2
    assert (
        page.locator(".ledger__head").evaluate("el => getComputedStyle(el).display")
        == "none"
    )


def test_a_row_renders_number_meta_record_and_tag(component):
    page = _row(component, sdot=True)

    assert page.locator(".ledger__row").evaluate("el => el.tagName") == "A"
    assert "01" in page.locator(".ledger__num").inner_text()
    assert page.locator(".ledger__date").inner_text() == "12 marzo"
    assert page.locator(".ledger__title").inner_text() == "Sessione"
    assert page.locator(".ledger__tag").evaluate("el => el.textContent") == "Bozza"


def test_the_second_date_line_is_optional(component):
    page = _row(component, meta="12 marzo", meta_extra="3 aprile 2026")

    assert "3 aprile 2026" in page.locator(".ledger__date").inner_text()


def test_an_absent_optional_cell_renders_nothing_not_none(component):
    """A published session has no tag, and a bare `{{ tag }}` prints "None"."""
    page = _row(component, tag=None, number=None, meta=None, meta_extra=None)

    row = page.locator(".ledger__row")
    assert "None" not in row.inner_text()
    assert row.locator(".ledger__tag").count() == 0
    assert row.locator(".ledger__num").inner_text() == ""
    assert row.locator(".ledger__date").inner_text() == ""


def test_the_ledger_row_hover_is_a_quiet_highlight(component):
    """A ledger row is a record, not an openable card: no hard-offset lift."""
    page = _row(component)
    row = page.locator(".ledger__row")

    row.hover()

    assert row.evaluate("el => getComputedStyle(el).transform") == "none"
    assert row.evaluate("el => getComputedStyle(el).backgroundColor") != (
        "rgba(0, 0, 0, 0)"
    )
