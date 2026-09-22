"""Character list composition: the create card *is* the collection.

F12 removes the masthead plus and renders ``editorial.CollectionCreate`` as a
grid cell beside the entity cards; when there are no characters the create card
is the only cell, so there is no empty panel with a second, separate action.
"""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.navigation import CardItem, Crumb, WorldContext

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


def _card(name: str) -> CardItem:
    return CardItem(
        name=name,
        href=f"/worlds/{WORLD_ID}/characters/{uuid4()}",
        tint="p8",
        title="Mercante del Guado",
        owner_label="Giocato da Ada",
    )


def _mount(component, cards: list[CardItem]):
    world = _world()
    return component.mount(
        "pages.characters.CharacterList",
        props={
            "world": world,
            "world_context": WorldContext(id=WORLD_ID, name=world.name, role="Master"),
            "nav": None,
            "cards": cards,
            "crumbs": [Crumb(label="Mondi", href="/worlds"), Crumb(label=world.name)],
            "pages": [],
            "drafts": None,
            "current_user": _user(),
        },
    )


def test_the_masthead_plus_is_gone(component):
    page = _mount(component, [_card("Uno")])

    assert page.locator(".masthead .btn-icon-only").count() == 0
    assert page.locator('.masthead [data-testid="create-character"]').count() == 0


def test_populated_puts_the_create_card_in_the_grid(component):
    page = _mount(component, [_card("Uno"), _card("Due")])

    assert page.locator(".grid > .entity-card").count() == 2
    create = page.locator(".grid > .collection-create")
    assert create.count() == 1
    assert create.evaluate("el => el.tagName") == "BUTTON"
    assert create.get_attribute("aria-label") == "Nuovo personaggio"
    assert create.get_attribute("data-testid") == "create-character"


def test_empty_renders_the_create_card_as_the_collection(component):
    page = _mount(component, [])

    assert page.locator(".empty-state").count() == 0
    assert page.locator(".grid > .entity-card").count() == 0

    create = page.locator(".grid > .collection-create")
    assert create.count() == 1
    assert create.evaluate("el => el.tagName") == "BUTTON"
    assert create.get_attribute("aria-label") == "Nuovo personaggio"
    assert "Nessun personaggio" in page.locator(".collection-create__hint").inner_text()
