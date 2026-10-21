"""Page outline and landmark names (REQ-0019/T08).

A collection under the masthead's h1 is a section, so its cards are h2. A draft
collection under the ``Bozze`` h2 is a subsection, so its cards are h3. The
rail and a document's related-material column are both complementary regions,
so each carries a name of its own; the names stay on the native elements
instead of a new role.
"""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.content.constants import ContentKind
from backend.content.references import Backlink
from backend.navigation import CardItem, Crumb, WorldContext

pytestmark = pytest.mark.frontend

WORLD_ID = "11111111-1111-1111-1111-111111111111"
RAIL_NAME = "Navigazione laterale"
ASIDE_NAME = "Materiale collegato"


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


def _common() -> dict:
    world = _world()
    return dict(
        world=world,
        world_context=WorldContext(id=WORLD_ID, name=world.name, role="Master"),
        nav=None,
        pages=[],
        crumbs=[Crumb(label="Mondi", href="/worlds"), Crumb(label=world.name)],
        current_user=_user(),
    )


def _backlinks() -> dict[ContentKind, list[Backlink]]:
    return {
        ContentKind.SESSION: [
            Backlink(
                kind=ContentKind.SESSION,
                name="Il risveglio della Marchesa",
                href=f"/worlds/{WORLD_ID}/sessions/{uuid4()}",
                tint="p1",
            )
        ]
    }


def _card(name: str) -> CardItem:
    return CardItem(
        name=name,
        href=f"/worlds/{WORLD_ID}/characters/{uuid4()}",
        tint="p8",
        title="Mercante del Guado",
        owner_label="Giocato da Ada",
    )


def _place(name: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        name=name,
        short_description="d",
        tint="p8",
        shape="rombo",
        image_url=None,
    )


def _outline(page) -> list[dict]:
    """The visible headings of the content, in document order."""
    return page.evaluate(
        """() => [...document.querySelectorAll('main h1, main h2, main h3, main h4, main h5, main h6')]
            .filter(h => !h.closest('dialog:not([open])'))
            .map(h => ({level: Number(h.tagName[1]), text: h.innerText.trim()}))"""
    )


def _assert_no_skipped_level(outline: list[dict]) -> None:
    levels = [entry["level"] for entry in outline]
    for earlier, later in zip(levels, levels[1:]):
        assert later - earlier <= 1, outline


COLLECTIONS = [
    ("pages.characters.CharacterList", "cards"),
    ("pages.npcs.NpcList", "cards"),
]


@pytest.mark.parametrize(("component_name", "key"), COLLECTIONS)
def test_the_collection_cards_are_sections_and_drafts_are_subsections(
    component, component_name, key
):
    page = component.mount(
        component_name,
        props={
            **_common(),
            key: [_card("Uno"), _card("Due")],
            "drafts": [_card("Bozza uno")],
        },
    )

    outline = _outline(page)
    assert outline[0]["level"] == 1
    assert [entry["text"] for entry in outline] == [
        outline[0]["text"],
        "Uno",
        "Due",
        "Bozze",
        "Bozza uno",
    ]
    assert [entry["level"] for entry in outline] == [1, 2, 2, 2, 3]
    _assert_no_skipped_level(outline)

    drafts = page.locator("section.section")
    assert drafts.locator("h2", has_text="Bozze").count() == 1
    assert drafts.locator(".entity-card h3.entity-card__name").count() == 1
    assert drafts.locator(".entity-card h2.entity-card__name").count() == 0


def test_the_atlas_keeps_its_sections_and_nests_its_drafts(component):
    page = component.mount(
        "pages.places.PlaceList",
        props={
            **_common(),
            "places": [_place("Radura"), _place("Guado")],
            "drafts": [_card("Bozza radura")],
            "current_place_id": None,
            "can_manage": False,
        },
    )

    outline = _outline(page)
    assert [entry["text"] for entry in outline] == [
        "Atlante dei luoghi",
        "Radura",
        "Le altre radure",
        "Bozze",
        "Bozza radura",
    ]
    assert [entry["level"] for entry in outline] == [1, 2, 2, 2, 3]
    _assert_no_skipped_level(outline)
    assert page.locator("section.section .entity-card h3").count() == 1


def _character_props() -> dict:
    return {
        **_common(),
        "character": SimpleNamespace(
            id=uuid4(),
            name="Fiamma Rossa",
            title="Mercante del Guado",
            short_description="Vende tutto.",
            body="Porta sale.",
            tint="p8",
            animal="🦊",
            image_url=None,
            locked=False,
            is_draft=False,
            version=1,
            owner=SimpleNamespace(name="Ada"),
        ),
        "can_manage": True,
        "animals": [],
        "tints": [],
        "links": _backlinks(),
        "short_html": "<p>Vende tutto.</p>",
        "body_html": "<p>Porta sale.</p>",
        "auto_edit": False,
    }


def _npc_props() -> dict:
    return {
        **_common(),
        "npc": SimpleNamespace(
            id=uuid4(),
            name="La Marchesa",
            title="Comandante",
            short_description="Presidia la radura.",
            body="È entrata nel bosco.",
            tint="p8",
            animal="🦉",
            image_url=None,
            locked=False,
            is_draft=False,
            version=1,
        ),
        "can_manage": True,
        "animals": [],
        "tints": [],
        "links": _backlinks(),
        "short_html": "<p>Presidia la radura.</p>",
        "body_html": "<p>È entrata nel bosco.</p>",
        "auto_edit": False,
    }


def _place_props() -> dict:
    return {
        **_common(),
        "place": SimpleNamespace(
            id=uuid4(),
            name="Radura della Grande Quercia",
            short_description="Dove il bosco si apre.",
            body="La quercia segna il centro.",
            tint="p1",
            shape="triangolo",
            image_url=None,
            locked=False,
            is_draft=False,
            version=1,
        ),
        "can_manage": True,
        "shapes": [],
        "tints": [],
        "is_current": False,
        "links": _backlinks(),
        "short_html": "<p>Dove il bosco si apre.</p>",
        "body_html": "<p>La quercia segna il centro.</p>",
        "auto_edit": False,
    }


def _story_props() -> dict:
    return {
        **_common(),
        "story": SimpleNamespace(
            id=uuid4(),
            title="L'inverno dei corvi",
            status="in_corso",
            period_label="Inverno, 4° anno",
            tint="p8",
            short_description="Il gelo chiude il fiume.",
            body="Ogni campagna ha un momento.",
            locked=False,
            is_draft=False,
            version=1,
            sessions=[
                SimpleNamespace(
                    id=uuid4(),
                    tint="p1",
                    in_world_date="Primavera, 3° anno",
                    title="Il risveglio della Marchesa",
                )
            ],
        ),
        "can_manage": True,
        "metadata": [],
        "links": _backlinks(),
        "short_html": "<p>Il gelo chiude il fiume.</p>",
        "body_html": "<p>Ogni campagna ha un momento.</p>",
        "auto_edit": False,
    }


def _session_props() -> dict:
    return {
        **_common(),
        "session": SimpleNamespace(
            id=uuid4(),
            title="Il pedaggio del Guado",
            in_world_date="Autunno, 3° anno",
            real_date=None,
            short_description="Tre fazioni firmano una tregua.",
            body="Al guado si presentano in tre.",
            tint="p5",
            locked=False,
            is_draft=False,
            version=1,
        ),
        "previous": None,
        "following": None,
        "can_manage": True,
        "metadata": [],
        "links": _backlinks(),
        "short_html": "<p>Tre fazioni firmano una tregua.</p>",
        "body_html": "<p>Al guado si presentano in tre.</p>",
        "auto_edit": False,
    }


def _page_props() -> dict:
    return {
        **_common(),
        "page": SimpleNamespace(
            id=uuid4(),
            title="Le regole della Casa",
            slug="le-regole-della-casa",
            menu_position=1,
            tint="p3",
            short_description="Regolamento e patti di tavolo.",
            body="Il manuale di Root resta il riferimento.",
            locked=False,
            is_draft=False,
            version=1,
        ),
        "others": [
            SimpleNamespace(
                slug="le-fazioni-del-boschetto", title="Le fazioni del Boschetto"
            )
        ],
        "can_manage": True,
        "metadata": [],
        "links": _backlinks(),
        "short_html": "<p>Regolamento e patti di tavolo.</p>",
        "body_html": "<p>Il manuale di Root resta il riferimento.</p>",
        "auto_edit": False,
    }


DOCUMENTS = [
    ("pages.characters.CharacterDetail", _character_props),
    ("pages.npcs.NpcDetail", _npc_props),
    ("pages.places.PlaceDetail", _place_props),
    ("pages.sessions.SessionDetail", _session_props),
    ("pages.stories.StoryDetail", _story_props),
    ("pages.pages.PageDetail", _page_props),
]


def test_the_showcase_nests_its_collection_specimens(component):
    """The design kit's h2 section keeps its cards and story at h3."""
    page = component.mount(
        "pages.showcase.Showcase",
        props={
            "users": [],
            "animals": [],
            "tints": [],
            "shapes": [],
            "button_group_views": [],
            "button_group_filters": [],
            "button_group_icons": [],
            "showcase_tabs": [],
            "showcase_people": [],
            "showcase_card": _card("Rugginosa"),
            "current_user": _user(),
        },
    )
    section = page.locator("section.showcase-section").filter(
        has=page.get_by_role("heading", name="Collection surfaces", exact=True)
    )

    assert section.locator("h2").count() == 1
    assert section.locator(".entity-card__name").evaluate_all(
        "els => els.map(el => el.tagName)"
    ) == ["H3", "H3"]
    assert section.locator(".story-card__title").evaluate("el => el.tagName") == "H3"


def test_the_settings_aside_is_named_by_its_visible_heading(component):
    world = _world()
    page = component.mount(
        "pages.worlds.WorldSettings",
        props={
            "world": SimpleNamespace(
                id=world.id,
                name=world.name,
                description="d",
                version=1,
                image_url=None,
            ),
            "members": [],
            "world_context": WorldContext(id=WORLD_ID, name=world.name, role="Master"),
            "nav": None,
            "crumbs": [Crumb(label="Mondi", href="/worlds"), Crumb(label=world.name)],
            "description_html": "<p>d</p>",
            "invites": [],
            "pages": [],
            "current_user": _user(),
        },
    )

    asides = page.locator("aside").evaluate_all(
        "els => els.map(el => el.getAttribute('aria-label'))"
    )
    assert asides == [RAIL_NAME, "Copertina"]
    assert page.get_by_role("complementary", name="Copertina").count() == 1
    aside = page.locator('aside[aria-label="Copertina"]')
    assert aside.locator("h2", has_text="Copertina").count() == 1

    outline = _outline(page)
    assert [entry["level"] for entry in outline] == [1, 2, 2, 2]
    _assert_no_skipped_level(outline)


@pytest.mark.parametrize(("component_name", "props"), DOCUMENTS)
def test_every_document_names_its_complementary_regions(
    component, component_name, props
):
    page = component.mount(component_name, props=props())

    asides = page.locator("aside").evaluate_all(
        "els => els.map(el => ({name: el.getAttribute('aria-label'), role: el.getAttribute('role')}))"
    )
    assert [aside["name"] for aside in asides] == [RAIL_NAME, ASIDE_NAME]
    assert all(aside["role"] is None for aside in asides), "an aside gained a role"

    assert page.get_by_role("complementary", name=RAIL_NAME).count() == 1
    assert page.get_by_role("complementary", name=ASIDE_NAME).count() == 1

    navs = page.locator("nav").evaluate_all(
        "els => els.map(el => el.getAttribute('aria-label'))"
    )
    assert all(navs), f"an unnamed navigation landmark: {navs}"
    assert len(set(navs)) == len(navs), f"two navigations share a name: {navs}"

    outline = _outline(page)
    assert [entry["level"] for entry in outline].count(1) == 1
    assert outline[0]["level"] == 1
    _assert_no_skipped_level(outline)
