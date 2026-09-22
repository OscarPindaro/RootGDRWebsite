"""Component tests for ``editorial.CollectionCreate``.

The F12 prototype: the literal creation card for a collection grid. The contract
these tests pin is the one the ticket asks the user to judge: a real button with
a clear accessible name, a visible focus ring, a hover that keeps its geometry,
and the footprint of exactly one entity-card cell.
"""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.navigation import CardItem, Crumb, WorldContext

pytestmark = pytest.mark.frontend

WORLD_ID = "11111111-1111-1111-1111-111111111111"
NEW_URL = f"/worlds/{WORLD_ID}/characters/new"


def _mount(component, **overrides):
    props = {"action": NEW_URL, "label": "Nuovo personaggio"}
    props.update(overrides)
    return component.mount("editorial.CollectionCreate", props=props)


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


def _card(name: str) -> CardItem:
    return CardItem(
        name=name,
        href=f"/worlds/{WORLD_ID}/characters/{uuid4()}",
        tint="p8",
        title="Mercante del Guado",
        owner_label="Giocato da Ada",
    )


def _list_props(cards: list[CardItem]) -> dict:
    world = _world()
    return {
        "world": world,
        "world_context": WorldContext(id=WORLD_ID, name=world.name, role="Master"),
        "nav": None,
        "cards": cards,
        "crumbs": [Crumb(label="Mondi", href="/worlds"), Crumb(label=world.name)],
        "pages": [],
        "drafts": None,
        "current_user": _user(),
    }


def test_it_is_a_real_button_with_an_accessible_name(component):
    page = _mount(component)

    button = page.get_by_role("button", name="Nuovo personaggio")
    assert button.count() == 1
    assert button.evaluate("el => el.tagName") == "BUTTON"
    assert button.get_attribute("type") == "button"
    assert button.get_attribute("hx-post") == NEW_URL
    assert button.get_attribute("hx-swap") == "none"


def test_the_hint_does_not_leak_into_the_accessible_name(component):
    page = _mount(component, hint="Nessun personaggio: creane uno per cominciare.")

    # The accessible name stays the label; the hint is visible prose only.
    assert page.get_by_role("button", name="Nuovo personaggio").count() == 1
    hint = page.locator(".collection-create__hint")
    assert "Nessun personaggio" in hint.inner_text()


def test_focus_is_visible_and_does_not_move_the_card(component):
    page = _mount(component)
    card = page.locator(".collection-create")
    before = card.bounding_box()

    page.keyboard.press("Tab")

    assert card.evaluate("el => el === document.activeElement")
    assert card.evaluate("el => getComputedStyle(el).outlineStyle") != "none"
    assert card.evaluate("el => getComputedStyle(el).outlineWidth") != "0px"
    assert card.bounding_box() == before


def test_hover_changes_the_surface_not_the_geometry(component):
    page = _mount(component)
    card = page.locator(".collection-create")
    before = card.bounding_box()
    resting = card.evaluate("el => getComputedStyle(el).backgroundColor")

    card.hover()

    assert card.evaluate("el => getComputedStyle(el).backgroundColor") != resting
    assert card.bounding_box() == before


def test_it_occupies_exactly_one_entity_card_cell(component):
    page = component.mount(
        "pages.characters.CharacterList",
        props=_list_props([_card("Uno"), _card("Due")]),
    )

    entity = page.locator(".grid > .card").first
    create = page.locator(".grid > .collection-create")
    assert create.count() == 1
    assert create.bounding_box()["width"] == pytest.approx(
        entity.bounding_box()["width"], abs=1
    )
