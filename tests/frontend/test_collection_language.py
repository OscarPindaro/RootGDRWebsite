"""The collection language is consistent where it should be.

The entity card, the story card, the ledger and the row are different
representations with their own density. What F14 made shared is the interaction
and state language: one visible focus ring, one hard-offset lift for the
openable card surfaces, one metadata line, and a quiet highlight (not a lift)
for the record rows. This file pins the consistency and the difference.
"""

from uuid import uuid4

import pytest

from backend.navigation import CardItem

pytestmark = pytest.mark.frontend

WORLD_ID = "11111111-1111-1111-1111-111111111111"


def _item() -> CardItem:
    return CardItem(
        name="Rugginosa",
        href=f"/worlds/{WORLD_ID}/characters/{uuid4()}",
        tint="p1",
        title="La Senza Tana",
        animal="gatto",
        owner_label="Giocato da Giulia",
    )


def _story(component):
    return component.mount(
        "editorial.StoryCard",
        props={
            "href": "#",
            "tint": "ochre",
            "title": "L'inverno dei corvi",
            "summary": "Un arco.",
            "status_label": "In corso",
            "session_count": 4,
        },
    )


def _outline(page, selector):
    page.keyboard.press("Tab")
    return page.locator(selector).evaluate(
        "el => [getComputedStyle(el).outlineStyle, "
        "getComputedStyle(el).outlineWidth, getComputedStyle(el).outlineColor]"
    )


def _meta(page, selector):
    return page.locator(selector).evaluate(
        "el => [getComputedStyle(el).fontFamily, getComputedStyle(el).color]"
    )


def test_the_openable_surfaces_share_one_lift(component):
    entity = component.mount("editorial.EntityCard", props={"item": _item()})
    entity.locator(".entity-card").hover()
    entity_style = entity.locator(".entity-card").evaluate(
        "el => [getComputedStyle(el).transform, getComputedStyle(el).boxShadow]"
    )

    story = _story(component)
    story.locator(".story-card").hover()
    story_style = story.locator(".story-card").evaluate(
        "el => [getComputedStyle(el).transform, getComputedStyle(el).boxShadow]"
    )

    assert entity_style == story_style
    assert entity_style[0] == "matrix(1, 0, 0, 1, -3, -3)"
    assert entity_style[1] != "none"


def test_every_openable_surface_shares_one_focus_ring(component):
    entity = component.mount("editorial.EntityCard", props={"item": _item()})
    entity_outline = _outline(entity, ".entity-card")

    story = _story(component)
    story_outline = _outline(story, ".story-card")

    create = component.mount(
        "editorial.CollectionCreate",
        props={"action": "/worlds/x/characters/new", "label": "Nuovo personaggio"},
    )
    create_outline = _outline(create, ".collection-create")

    assert entity_outline == story_outline == create_outline
    assert entity_outline[0] != "none"


def test_the_metadata_line_reads_the_same(component):
    entity = component.mount("editorial.EntityCard", props={"item": _item()})
    entity_meta = _meta(entity, ".entity-card__owner")

    story = _story(component)
    story_meta = _meta(story, ".story-card__foot")

    ledger = component.mount(
        "editorial.LedgerRow",
        props={"href": "#", "title": "Sessione", "number": "01", "meta": "12 marzo"},
    )
    ledger_meta = _meta(ledger, ".ledger__num")

    row = component.mount(
        "editorial.Row",
        props={"href": "#", "name": "Radura", "meta": "Scena corrente"},
    )
    row_meta = _meta(row, ".row__meta")

    assert entity_meta == story_meta == ledger_meta == row_meta
    assert "Plex Mono" in entity_meta[0]


def test_the_record_rows_keep_their_own_density(component):
    """A ledger is not a story is not a card: the layout stays per-representation."""
    ledger = component.mount(
        "editorial.LedgerRow",
        props={"href": "#", "title": "Sessione", "number": "01", "meta": "12 marzo"},
    )
    ledger_columns = ledger.locator(".ledger__row").evaluate(
        "el => getComputedStyle(el).gridTemplateColumns"
    )
    assert len(ledger_columns.split()) == 4
    assert ledger.locator(".story-card").count() == 0
    assert ledger.locator(".entity-card").count() == 0

    row = component.mount(
        "editorial.Row", props={"href": "#", "name": "Radura", "meta": "x"}
    )
    row_columns = row.locator(".row").evaluate(
        "el => getComputedStyle(el).gridTemplateColumns"
    )
    assert len(row_columns.split()) == 3
    assert row.locator(".story-card").count() == 0

    story = _story(component)
    assert story.locator(".story-band").count() == 1
    assert story.locator(".entity-card__media").count() == 0

    entity = component.mount("editorial.EntityCard", props={"item": _item()})
    assert entity.locator(".entity-card__media").count() == 1
    assert entity.locator(".story-band").count() == 0
