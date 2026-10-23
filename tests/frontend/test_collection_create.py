"""Component tests for ``editorial.CollectionCreate``.

The F12 prototype: the literal creation card for a collection grid. The contract
these tests pin is the one the ticket asks the user to judge: a real button with
a clear accessible name, a visible focus ring, a hover that keeps its geometry,
and the footprint of exactly one entity-card cell.

REQ-0019/T27 adds the phone placement: below 700px the colocated script moves
the same button above the grid as a compact labelled action row, and at 701px
and above it is the grid's last cell again.
"""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.navigation import CardItem, Crumb, WorldContext

pytestmark = pytest.mark.frontend

WORLD_ID = "11111111-1111-1111-1111-111111111111"
NEW_URL = f"/worlds/{WORLD_ID}/characters/new"
PHONE = {"width": 390, "height": 844}
DESKTOP = {"width": 1440, "height": 1000}


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


def test_focus_is_visible_without_resizing_the_card(component):
    page = _mount(component)
    card = page.locator(".collection-create")
    before = card.bounding_box()

    page.keyboard.press("Tab")

    assert card.evaluate("el => el === document.activeElement")
    assert card.evaluate("el => getComputedStyle(el).outlineStyle") != "none"
    assert card.evaluate("el => getComputedStyle(el).outlineWidth") != "0px"
    # Focusing must not resize the card; where it sits on screen may shift if
    # the browser scrolls it into view.
    after = card.bounding_box()
    assert after["width"] == pytest.approx(before["width"], abs=0.5)
    assert after["height"] == pytest.approx(before["height"], abs=0.5)


def test_the_card_is_a_missing_card_not_a_filled_one(component):
    """Dashed ink frame and a transparent fill, so the page shows through."""
    page = _mount(component)
    card = page.locator(".collection-create")

    assert card.evaluate("el => getComputedStyle(el).borderTopStyle") == "dashed"
    assert card.evaluate("el => getComputedStyle(el).backgroundColor") == (
        "rgba(0, 0, 0, 0)"
    )


def test_hover_lifts_the_card_exactly_like_an_entity_card(component):
    """The two read as peers, so they share one hover."""
    page = component.mount(
        "pages.characters.CharacterList",
        props=_list_props([_card("Uno")]),
        reduced_motion=True,
    )
    create = page.locator(".collection-create")
    entity = page.locator(".grid > .entity-card").first

    create.hover()
    lifted = create.evaluate(
        "el => [getComputedStyle(el).transform, getComputedStyle(el).boxShadow]"
    )
    entity.hover()
    peer = entity.evaluate(
        "el => [getComputedStyle(el).transform, getComputedStyle(el).boxShadow]"
    )

    assert lifted == peer
    assert lifted[0] != "none"


def test_the_card_mirrors_an_entity_card_structure(component):
    """Same media ratio and same body box as an entity card, so a shared grid row
    stretches the two to the same height."""
    page = component.mount(
        "pages.characters.CharacterList",
        props=_list_props([_card("Uno")]),
    )
    card_media = page.locator(".collection-create__media")
    card_body = page.locator(".collection-create__body")
    entity_media = page.locator(".grid > .entity-card .entity-card__media")
    entity_body = page.locator(".grid > .entity-card .entity-card__body")

    assert card_media.evaluate(
        "el => getComputedStyle(el).aspectRatio"
    ) == entity_media.evaluate("el => getComputedStyle(el).aspectRatio")
    for edge in ("paddingLeft", "paddingRight", "paddingBottom"):
        assert card_body.evaluate(
            f"el => getComputedStyle(el).{edge}"
        ) == entity_body.evaluate(f"el => getComputedStyle(el).{edge}")


def test_it_occupies_exactly_one_entity_card_cell(component):
    page = component.mount(
        "pages.characters.CharacterList",
        props=_list_props([_card("Uno"), _card("Due")]),
    )

    entity = page.locator(".grid > .entity-card").first
    create = page.locator(".grid > .collection-create")
    assert create.count() == 1
    assert create.bounding_box()["width"] == pytest.approx(
        entity.bounding_box()["width"], abs=1
    )


def test_pressing_settles_the_lift_back_onto_the_page(component):
    """The shared entry owns the pressed state, not the page."""
    page = component.mount(
        "editorial.CollectionCreate",
        props={"action": NEW_URL, "label": "Nuovo personaggio"},
        reduced_motion=True,
    )
    card = page.locator(".collection-create")
    box = card.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    card.hover()
    assert card.evaluate("el => getComputedStyle(el).transform") != "none"

    page.mouse.down()
    try:
        assert card.evaluate("el => getComputedStyle(el).transform") == (
            "matrix(1, 0, 0, 1, 0, 0)"
        )
        assert card.evaluate("el => getComputedStyle(el).boxShadow") == "none"
    finally:
        page.mouse.up()


def test_a_disabled_entry_keeps_its_geometry_and_drops_the_action(component):
    page = _mount(component, disabled=True)
    card = page.locator(".collection-create")

    assert card.evaluate("el => el.tagName") == "BUTTON"
    assert card.get_attribute("disabled") is not None
    assert card.get_attribute("hx-post") is None
    card.hover()
    assert card.evaluate("el => getComputedStyle(el).transform") == "none"
    assert card.evaluate("el => getComputedStyle(el).boxShadow") == "none"


def _mount_list(component, cards, *, viewport=None):
    page = component.mount(
        "pages.characters.CharacterList",
        props=_list_props(cards),
        reduced_motion=True,
    )
    if viewport is not None:
        page.set_viewport_size(viewport)
        page.reload()
    return page


def test_below_700px_the_entry_is_the_collections_action_row(component):
    page = _mount_list(component, [_card("Uno"), _card("Due")], viewport=PHONE)
    create = page.locator('[data-testid="create-character"]')

    assert create.evaluate("el => el.parentElement.className") == "container"
    assert create.evaluate("el => el.nextElementSibling.classList.contains('grid')")
    assert create.evaluate("el => el.hasAttribute('data-collection-action')")
    assert create.evaluate("el => getComputedStyle(el).display") == "flex"

    box = create.bounding_box()
    assert 44 <= box["height"] < 120
    assert box["width"] == pytest.approx(
        page.locator(".grid").bounding_box()["width"], abs=1
    )


def test_the_phone_row_precedes_every_card(component):
    cards = [_card(f"Personaggio {index}") for index in range(30)]
    page = _mount_list(component, cards, viewport=PHONE)

    create = page.locator('[data-testid="create-character"]')
    first = page.locator(".grid > .entity-card").first
    create_box = create.bounding_box()
    assert create_box["y"] + create_box["height"] <= first.bounding_box()["y"]
    # The entry is in the first phone screen; the cards are not what brings it
    # there.
    assert create_box["y"] + create_box["height"] <= 844


def test_the_phone_row_is_first_in_the_focus_order(component):
    cards = [_card(f"Personaggio {index}") for index in range(30)]
    page = _mount_list(component, cards, viewport=PHONE)

    reached = None
    for count in range(1, 30):
        page.keyboard.press("Tab")
        if page.evaluate(
            "() => document.activeElement?.dataset.testid === 'create-character'"
        ):
            reached = count
            break

    assert reached is not None, "the creation entry was not reached by keyboard"
    assert reached <= 15
    assert page.evaluate(
        """() => {
            const create = document.querySelector('[data-testid="create-character"]');
            const card = document.querySelector('.grid > .entity-card');
            return Boolean(
                create.compareDocumentPosition(card)
                & Node.DOCUMENT_POSITION_FOLLOWING
            );
        }"""
    )


def test_the_empty_phone_row_keeps_the_hint_on_screen(component):
    page = _mount_list(component, [], viewport=PHONE)

    create = page.locator('[data-testid="create-character"]')
    hint = page.locator(".collection-create__hint")
    assert "Nessun personaggio" in hint.inner_text()
    assert hint.is_visible()
    hint_box = hint.bounding_box()
    assert hint_box["y"] + hint_box["height"] <= 844
    assert create.bounding_box()["height"] < 160


def test_701px_and_above_restores_the_last_grid_cell(component):
    page = _mount_list(component, [_card("Uno")], viewport=PHONE)
    create = page.locator('[data-testid="create-character"]')
    assert not create.evaluate("el => el.parentElement.classList.contains('grid')")

    page.set_viewport_size({"width": 701, "height": 1000})
    page.wait_for_function(
        "() => document.querySelector('[data-testid=\"create-character\"]')"
        ".parentElement.classList.contains('grid')"
    )

    assert not create.evaluate("el => el.hasAttribute('data-collection-action')")
    assert create.evaluate("el => el === el.parentElement.lastElementChild")
    assert create.evaluate("el => getComputedStyle(el).display") == "grid"


def test_the_move_keeps_one_button_with_the_same_action(component):
    page = _mount_list(component, [_card("Uno")], viewport=PHONE)

    assert page.locator(".collection-create").count() == 1
    create = page.locator('[data-testid="create-character"]')
    assert create.count() == 1
    assert create.get_attribute("hx-post") == NEW_URL
    assert create.get_attribute("hx-swap") == "none"
    assert create.get_attribute("aria-label") == "Nuovo personaggio"


def test_a_focused_entry_keeps_focus_when_the_placement_changes(component):
    page = _mount_list(component, [_card("Uno")], viewport=PHONE)
    create = page.locator('[data-testid="create-character"]')
    create.focus()
    assert create.evaluate("el => el === document.activeElement")

    page.set_viewport_size(DESKTOP)
    page.wait_for_function(
        "() => document.querySelector('[data-testid=\"create-character\"]')"
        ".parentElement.classList.contains('grid')"
    )

    assert page.evaluate(
        "() => document.activeElement?.dataset.testid === 'create-character'"
    )


def _mount_npcs(component, cards, *, can_manage):
    world = _world()
    page = component.mount(
        "pages.npcs.NpcList",
        props={
            "world": world,
            "world_context": WorldContext(id=WORLD_ID, name=world.name, role="Master"),
            "nav": None,
            "cards": cards,
            "crumbs": [Crumb(label="Mondi", href="/worlds"), Crumb(label=world.name)],
            "can_manage": can_manage,
            "pages": [],
            "drafts": None,
            "current_user": _user(),
        },
    )
    page.set_viewport_size(PHONE)
    page.reload()
    return page


def test_the_npc_collection_uses_the_same_phone_entry(component):
    page = _mount_npcs(component, [_card("Uno")], can_manage=True)
    create = page.locator('[data-testid="create-npc"]')

    assert create.evaluate("el => el.parentElement.className") == "container"
    assert create.evaluate("el => el.hasAttribute('data-collection-action')")
    assert 44 <= create.bounding_box()["height"] < 120


def test_a_reader_is_still_not_handed_an_npc_entry(component):
    page = _mount_npcs(component, [], can_manage=False)

    assert page.locator('[data-testid="create-npc"]').count() == 0
    assert page.locator(".empty-state").count() == 1
