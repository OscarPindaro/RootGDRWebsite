"""The document layout: one main child, one optional aside stack.

Character, NPC, Place, Story, Session and Page details share one composition
contract — ``common.Grid`` with ``document``. Before it, three of them nested
the backlinks panel inside the main column (and never closed ``.docpage``),
Story could emit two competing grid children, and Page left its backlinks
outside the grid entirely.
"""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.content.constants import ContentKind
from backend.content.references import Backlink
from backend.content.view_helpers import animal_options, shape_options, tint_options
from backend.navigation import Crumb, WorldContext

pytestmark = pytest.mark.frontend

WORLD_ID = "11111111-1111-1111-1111-111111111111"
PHONE = {"width": 390, "height": 844}


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
        short_html="<p>Breve.</p>",
        body_html="<p>Corpo.</p>",
        auto_edit=False,
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


def _character_props(links=None) -> dict:
    return {
        **_common(),
        "character": SimpleNamespace(
            id=uuid4(),
            name="Fiamma Rossa",
            title="Mercante del Guado",
            short_description="Vende tutto, comprese le informazioni.",
            body="Porta sale a @[Il Cerchio di Pietre].",
            tint="p8",
            animal="🦊",
            image_url=None,
            locked=False,
            is_draft=False,
            version=1,
            owner=SimpleNamespace(name="Ada"),
        ),
        "can_manage": True,
        "animals": animal_options(),
        "tints": tint_options(),
        "links": links,
    }


def _npc_props(links=None) -> dict:
    return {
        **_common(),
        "npc": SimpleNamespace(
            id=uuid4(),
            name="La Marchesa",
            title="Comandante delle truppe feline",
            short_description="Presidia la radura e vuole il pedaggio.",
            body="È entrata nel bosco in primavera.",
            tint="p8",
            animal="🦉",
            image_url=None,
            locked=False,
            is_draft=False,
            version=1,
        ),
        "can_manage": True,
        "animals": animal_options(),
        "tints": tint_options(),
        "links": links,
    }


def _place_props(links=None) -> dict:
    return {
        **_common(),
        "place": SimpleNamespace(
            id=uuid4(),
            name="Radura della Grande Quercia",
            short_description="Dove il bosco si apre.",
            body="La quercia segna il centro del bosco.",
            tint="p1",
            shape="triangolo",
            image_url=None,
            locked=False,
            is_draft=False,
            version=1,
        ),
        "can_manage": True,
        "shapes": shape_options(),
        "tints": tint_options(),
        "is_current": False,
        "links": links,
    }


def _story_props(*, sessions, links=None) -> dict:
    return {
        **_common(),
        "story": SimpleNamespace(
            id=uuid4(),
            title="L'inverno dei corvi",
            status="in_corso",
            period_label="Inverno, 4° anno",
            tint="p8",
            short_description="Il gelo chiude il fiume.",
            body="Ogni campagna ha un momento in cui le regole smettono di bastare.",
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
            ]
            if sessions
            else [],
        ),
        "can_manage": True,
        "metadata": [],
        "links": links,
    }


def _session_props(links=None) -> dict:
    return {
        **_common(),
        "session": SimpleNamespace(
            id=uuid4(),
            title="Il pedaggio del Guado",
            in_world_date="Autunno, 3° anno",
            real_date=None,
            short_description="Tre fazioni firmano una tregua di una stagione.",
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
        "links": links,
    }


def _page_props(links=None) -> dict:
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
        "links": links,
    }


def _children(page) -> list[dict]:
    """The document grid's direct children, with their geometry."""
    return page.evaluate(
        """() => {
            const grid = document.querySelector('.grid-document');
            if (!grid) return [];
            return [...grid.children].map(child => {
                const rect = child.getBoundingClientRect();
                return {
                    tag: child.tagName,
                    x: rect.x,
                    y: rect.y,
                    width: rect.width,
                    height: rect.height,
                    text: child.innerText || '',
                    hasLinks: !!child.querySelector('.links'),
                    hasPager: !!child.querySelector('.pager'),
                    hasToc: !!child.querySelector('.toc'),
                };
            });
        }"""
    )


def _assert_single_column(page) -> None:
    children = _children(page)

    assert len(children) == 1, f"expected a lone main child, got {children}"


@pytest.mark.parametrize(
    ("component_name", "props"),
    [
        ("pages.characters.CharacterDetail", _character_props),
        ("pages.npcs.NpcDetail", _npc_props),
        ("pages.places.PlaceDetail", _place_props),
        ("pages.sessions.SessionDetail", _session_props),
    ],
)
def test_the_backlinks_are_the_direct_right_column_child(
    component, component_name, props
):
    page = component.mount(component_name, props=props(links=_backlinks()))
    main, aside = _children(page)

    assert aside["hasLinks"], "the backlinks panel is not in the aside"
    assert not main["hasLinks"], "the backlinks panel is still inside the main column"
    assert aside["x"] >= main["x"] + main["width"], "the aside is not to the right"


@pytest.mark.parametrize(
    ("component_name", "props"),
    [
        ("pages.characters.CharacterDetail", _character_props),
        ("pages.npcs.NpcDetail", _npc_props),
        ("pages.places.PlaceDetail", _place_props),
        ("pages.sessions.SessionDetail", _session_props),
    ],
)
def test_a_document_without_backlinks_has_one_column(component, component_name, props):
    page = component.mount(component_name, props=props(links=None))

    _assert_single_column(page)


def test_the_aside_stacks_below_the_document_on_a_phone(component):
    page = component.mount(
        "pages.characters.CharacterDetail", props=_character_props(links=_backlinks())
    )
    page.set_viewport_size(PHONE)
    main, aside = _children(page)

    assert aside["y"] >= main["y"] + main["height"], "the aside did not move below"
    assert abs(aside["x"] - main["x"]) < 2, "the aside kept its own column"
    assert aside["width"] == main["width"], "the aside did not take the full width"


def test_a_story_shares_one_aside_stack_with_its_sessions(component):
    page = component.mount(
        "pages.stories.StoryDetail",
        props=_story_props(sessions=True, links=_backlinks()),
    )
    main, aside = _children(page)
    text = aside["text"].lower()

    assert "sessioni incluse" in text, "the sessions panel is not in the aside"
    assert "collegamenti" in text, "the backlinks are not in the same aside"
    assert not main["hasLinks"], "the backlinks are still a second grid child"
    assert aside["x"] >= main["x"] + main["width"]


def test_a_story_without_sessions_or_backlinks_has_one_column(component):
    page = component.mount(
        "pages.stories.StoryDetail", props=_story_props(sessions=False, links=None)
    )

    _assert_single_column(page)


def test_a_session_keeps_its_pager_in_the_main_column(component):
    page = component.mount(
        "pages.sessions.SessionDetail", props=_session_props(links=_backlinks())
    )
    main, aside = _children(page)

    assert main["hasPager"], "the pager left the document column"
    assert not aside["hasPager"], "the pager ended up in the aside"
    assert aside["hasLinks"]


def test_a_page_merges_altre_pagine_and_backlinks_into_one_aside(component):
    page = component.mount(
        "pages.pages.PageDetail", props=_page_props(links=_backlinks())
    )
    main, aside = _children(page)

    assert aside["hasToc"], "Altre pagine left the aside"
    assert aside["hasLinks"], "the backlinks are not in the same aside"
    assert not main["hasToc"] and not main["hasLinks"]


def test_every_detail_page_uses_the_same_breakpoint(component):
    """The aside is beside the document above 700px and below it at the phone."""
    for component_name, props in (
        ("pages.characters.CharacterDetail", _character_props(links=_backlinks())),
        ("pages.places.PlaceDetail", _place_props(links=_backlinks())),
        ("pages.pages.PageDetail", _page_props(links=_backlinks())),
    ):
        page = component.mount(component_name, props=props)
        page.set_viewport_size({"width": 800, "height": 900})
        main, aside = _children(page)
        assert aside["x"] >= main["x"] + main["width"], f"{component_name} at 800px"

        page.set_viewport_size(PHONE)
        main, aside = _children(page)
        assert aside["y"] >= main["y"] + main["height"], f"{component_name} at 390px"
