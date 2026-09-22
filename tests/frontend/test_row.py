"""Component tests for ``editorial.RowList`` and ``editorial.Row``.

The atlas of places and the draft lists read as rows: a mark, a name and
description, and a meta cell. F14 extracted the structure so the atlas and the
three draft lists share one row without any of them becoming a card.
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


def _place(name: str, *, current: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4() if not current else uuid4(),
        name=name,
        short_description="Una radura del bosco.",
        tint="forest",
        shape="rombo",
        image_url=None,
    )


def _place_page(component, places, current_place_id=None):
    world = _world()
    return component.mount(
        "pages.places.PlaceList",
        props={
            "world": world,
            "world_context": WorldContext(id=WORLD_ID, name=world.name, role="Master"),
            "nav": None,
            "places": places,
            "current_place_id": current_place_id,
            "crumbs": [Crumb(label="Mondi", href="/worlds"), Crumb(label=world.name)],
            "pages": [],
            "drafts": None,
            "can_manage": True,
            "current_user": _user(),
        },
    )


def _row(component, **overrides):
    props = dict(href="#", name="Radura", description="Una radura.", meta=None)
    props.update(overrides)
    return component.mount("editorial.Row", props=props)


def test_the_places_page_is_an_atlas_of_rows(component):
    page = _place_page(component, [_place("Prima"), _place("Seconda")])

    assert page.locator(".feature").count() == 1
    assert page.locator(".row-list").count() == 1
    assert page.locator(".row").count() == 1
    # No entity card: the atlas is not a card grid.
    assert page.locator(".entity-card").count() == 0


def test_a_row_carries_name_description_and_meta(component):
    page = _row(component, meta="Scena corrente")

    assert page.locator(".row").evaluate("el => el.tagName") == "A"
    assert page.locator(".row__name").inner_text() == "Radura"
    assert page.locator(".row__desc").inner_text() == "Una radura."
    assert page.locator(".row__meta").inner_text() == "Scena corrente"


def test_a_draft_row_uses_the_shared_draft_pill(component):
    page = _row(component, draft=True)

    assert page.locator(".row__meta .pill-draft").count() == 1


def test_the_row_hover_is_a_quiet_highlight(component):
    """A row is a record, not an openable card: no hard-offset lift."""
    page = _row(component)
    row = page.locator(".row")

    row.hover()

    assert row.evaluate("el => getComputedStyle(el).transform") == "none"
    assert row.evaluate("el => getComputedStyle(el).backgroundColor") != (
        "rgba(0, 0, 0, 0)"
    )


def test_the_caller_supplies_the_mark_as_content(component):
    page = component.mount(
        "editorial.Row",
        props={"href": "#", "name": "Radura"},
        content='<span class="plogo" aria-hidden="true"></span>',
    )

    assert page.locator(".row > .plogo").count() == 1
