"""Component tests for ``editorial.StoryCard`` and ``editorial.StoryBand``.

A story stays a band: the act strip names the status, the body carries the title
and summary, and the foot the session count and the draft state. F14 extracted
the structure so the list page and the overview column share it without either
turning into a card.
"""

from types import SimpleNamespace

import pytest

from backend.navigation import Crumb, WorldContext
from backend.worlds.overview import Teaser, WorldOverview

pytestmark = pytest.mark.frontend

WORLD_ID = "11111111-1111-1111-1111-111111111111"


def _props(**overrides) -> dict:
    props = dict(
        href="/worlds/1/stories/1",
        tint="ochre",
        title="L'inverno dei corvi",
        summary="Un arco che raccoglie le sessioni della campagna.",
        status_label="In corso",
        period_label="Anno 3",
        session_count=4,
        draft=False,
        level=2,
    )
    props.update(overrides)
    return props


def test_a_story_stays_a_band(component):
    page = component.mount("editorial.StoryCard", props=_props())

    assert page.locator(".story-card").count() == 1
    assert page.locator(".story-card .story-band").count() == 1
    assert page.locator(".story-card__body").count() == 1
    # It does not borrow the entity card's root.
    assert page.locator(".entity-card").count() == 0


def test_the_band_names_the_status_and_the_period(component):
    page = component.mount("editorial.StoryCard", props=_props())

    band = page.locator(".story-band").evaluate("el => el.textContent")
    assert "In corso" in band
    assert "Anno 3" in band


def test_the_band_carries_the_tint(component):
    page = component.mount("editorial.StoryCard", props=_props())

    background = page.locator(".story-band").evaluate(
        "el => getComputedStyle(el).backgroundColor"
    )
    assert background != "rgba(0, 0, 0, 0)"


def test_the_foot_keeps_the_session_count_and_marks_a_draft(component):
    page = component.mount("editorial.StoryCard", props=_props(draft=True))

    assert "4 sessioni" in page.locator(".story-card__foot").inner_text()
    assert page.locator(".story-card__foot .pill-draft").count() == 1


def test_a_published_story_has_no_draft_pill(component):
    page = component.mount("editorial.StoryCard", props=_props())

    assert page.locator(".pill-draft").count() == 0


def test_level_three_keeps_the_overview_outline(component):
    page = component.mount("editorial.StoryCard", props=_props(level=3))

    assert page.locator("h3.story-card__title").count() == 1
    assert page.locator("h2.story-card__title").count() == 0


def test_the_inline_band_is_the_document_badge(component):
    page = component.mount(
        "editorial.StoryBand",
        props={"status": "Chiusa", "tint": "cobalt", "inline": True},
    )

    assert page.locator(".story-band--inline").count() == 1
    assert (
        page.locator(".story-band").evaluate("el => getComputedStyle(el).display")
        == "inline-flex"
    )


def test_the_overview_passes_the_heading_level_as_a_number(component):
    """A literal JinjaX prop is a string; the page must pass an int.

    ``level=3`` would arrive as ``"3"`` and render an h2, so the overview column
    would break the page outline. The page passes ``level={{ 3 }}``.
    """
    world = SimpleNamespace(
        id=WORLD_ID, name="Il Boschetto di Smeraldo", description="d", version=1
    )
    page = component.mount(
        "pages.worlds.WorldOverview",
        props={
            "world": world,
            "world_context": WorldContext(id=WORLD_ID, name=world.name, role="Master"),
            "nav": None,
            "quicks": [],
            "overview": WorldOverview(
                counts={},
                diary=[],
                open_story=Teaser(
                    kind="In corso",
                    title="L'inverno dei corvi",
                    href="/worlds/1/stories/1",
                    description="d",
                    tint="ochre",
                ),
                current_place=None,
            ),
            "crumbs": [Crumb(label="Mondi", href="/worlds")],
            "pages": [],
            "current_user": SimpleNamespace(
                name="Ada",
                email="ada@example.com",
                role="admin",
                avatar_url=None,
                symbol_style="icons",
            ),
        },
    )

    assert page.locator("h3.story-card__title").count() == 1
    assert page.locator("h2.story-card__title").count() == 0
