"""Character list composition: the create card *is* the collection.

F12 removes the masthead plus and renders ``editorial.CollectionCreate`` as a
grid cell beside the entity cards; when there are no characters the create card
is the only cell, so there is no empty panel with a second, separate action.

REQ-0019/T27 moves that same entry above the grid below 700px, where a growing
collection would otherwise put it thousands of pixels down the page.
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


def _mount_at(component, cards, *, width=390, height=844):
    page = _mount(component, cards)
    page.set_viewport_size({"width": width, "height": height})
    page.reload()
    return page


def test_phone_puts_the_entry_above_the_collection(component):
    page = _mount_at(component, [_card("Uno"), _card("Due")])

    assert page.locator(".grid > .collection-create").count() == 0
    create = page.locator('[data-testid="create-character"]')
    assert create.evaluate("el => el.parentElement.className") == "container"
    assert create.evaluate("el => el.nextElementSibling.classList.contains('grid')")
    assert page.locator(".grid > .entity-card").count() == 2


def test_phone_keeps_the_empty_explanation_visible(component):
    page = _mount_at(component, [])

    assert page.locator(".empty-state").count() == 0
    hint = page.locator(".collection-create__hint")
    assert "Nessun personaggio" in hint.inner_text()
    box = hint.bounding_box()
    assert box["y"] + box["height"] <= 844


def test_phone_long_collection_keeps_the_entry_in_the_first_screen(component):
    cards = [_card(f"Personaggio {index}") for index in range(30)]
    page = _mount_at(component, cards)

    create = page.locator('[data-testid="create-character"]')
    box = create.bounding_box()
    assert box["y"] + box["height"] <= 844
    assert page.locator(".grid > .entity-card").count() == 30
    assert page.locator(".masthead .btn-icon-only").count() == 0


@pytest.mark.parametrize("width", (320, 390))
def test_phone_does_not_scroll_sideways(component, width):
    page = _mount_at(
        component, [_card("Uno")], width=width, height=700 if width == 320 else 844
    )

    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_desktop_keeps_the_entry_as_the_last_grid_cell(component):
    page = _mount_at(component, [_card("Uno")], width=1440, height=1000)

    create = page.locator(".grid > .collection-create")
    assert create.count() == 1
    assert create.evaluate("el => el === el.parentElement.lastElementChild")
    assert page.locator(".container > .collection-create").count() == 0
