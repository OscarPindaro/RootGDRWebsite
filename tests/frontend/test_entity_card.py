"""Component tests for ``editorial.EntityCard``.

The entity card is the product's portrait card. F14 renamed it off ``.card`` so
it no longer shares a root selector with the generic ``common.Card`` container,
and moved its rules out of ``main.css``. It keeps the media ratio and the body
box that the creation card mirrors, and the shared openable hover.
"""

from uuid import uuid4

import pytest

from backend.navigation import CardItem

pytestmark = pytest.mark.frontend

WORLD_ID = "11111111-1111-1111-1111-111111111111"


def _item(**overrides) -> CardItem:
    props = dict(
        name="Rugginosa",
        href=f"/worlds/{WORLD_ID}/characters/{uuid4()}",
        tint="p1",
        title="La Senza Tana",
        animal="gatto",
        owner_label="Giocato da Giulia",
    )
    props.update(overrides)
    return CardItem(**props)


def _mount(component, **overrides):
    return component.mount("editorial.EntityCard", props={"item": _item(**overrides)})


def test_it_is_an_entity_card_not_a_common_card(component):
    page = _mount(component)

    assert page.locator(".entity-card").count() == 1
    # The generic Card root is gone, so the two components share no selector.
    assert page.locator(".card").count() == 0


def test_it_links_and_names_the_character(component):
    page = _mount(component)
    card = page.locator(".entity-card")

    assert card.evaluate("el => el.tagName") == "A"
    assert card.get_attribute("href").startswith(f"/worlds/{WORLD_ID}/characters/")
    assert page.locator(".entity-card__name").inner_text() == "Rugginosa"
    assert page.locator(".entity-card__title").inner_text() == "La Senza Tana"
    assert page.locator(".entity-card__owner").inner_text() == "Giocato da Giulia"


def test_optional_title_and_owner_are_omitted(component):
    page = component.mount(
        "editorial.EntityCard",
        props={"item": CardItem(name="Senza titolo", href="#", tint="p1")},
    )

    assert page.locator(".entity-card__title").count() == 0
    assert page.locator(".entity-card__owner").count() == 0


def test_the_media_uses_the_shared_portrait_ratio(component):
    page = _mount(component)

    assert (
        page.locator(".entity-card__media").evaluate(
            "el => getComputedStyle(el).aspectRatio"
        )
        == "4 / 5"
    )


def test_an_npc_card_carries_the_badge_and_a_dashed_owner_rule(component):
    page = component.mount("editorial.EntityCard", props={"item": _item(), "npc": True})

    assert page.locator(".entity-card--npc").count() == 1
    badge = page.locator(".entity-card__name").evaluate(
        "el => getComputedStyle(el, '::after').content"
    )
    assert "NPC" in badge
    assert (
        page.locator(".entity-card__owner").evaluate(
            "el => getComputedStyle(el).borderTopStyle"
        )
        == "dashed"
    )


def test_hover_lifts_onto_the_shared_hard_offset(component):
    page = _mount(component)
    card = page.locator(".entity-card")

    card.hover()

    assert card.evaluate("el => getComputedStyle(el).transform") == (
        "matrix(1, 0, 0, 1, -3, -3)"
    )
    assert card.evaluate("el => getComputedStyle(el).boxShadow") != "none"


def test_pressing_settles_the_lift_back_onto_the_page(component):
    # href="#" so completing the click does not navigate away from the shell.
    page = _mount(component, href="#")
    card = page.locator(".entity-card")
    box = card.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    card.hover()
    page.mouse.down()
    try:
        assert card.evaluate("el => getComputedStyle(el).transform") == (
            "matrix(1, 0, 0, 1, 0, 0)"
        )
        assert card.evaluate("el => getComputedStyle(el).boxShadow") == "none"
    finally:
        page.mouse.up()


def test_focus_is_visible_without_resizing_the_card(component):
    page = _mount(component)
    card = page.locator(".entity-card")
    before = card.bounding_box()

    page.keyboard.press("Tab")

    assert card.evaluate("el => el === document.activeElement")
    assert card.evaluate("el => getComputedStyle(el).outlineStyle") != "none"
    after = card.bounding_box()
    assert after["width"] == pytest.approx(before["width"], abs=0.5)
    assert after["height"] == pytest.approx(before["height"], abs=0.5)
