"""The document layout: one main child, one optional aside stack.

Character, NPC, Place, Story, Session and Page details share one composition
contract — ``common.Grid`` with ``document``. Before it, three of them nested
the backlinks panel inside the main column (and never closed ``.docpage``),
Story could emit two competing grid children, and Page left its backlinks
outside the grid entirely.

The matrix below mounts every one of the six real pages with and without
related material and with a long title, at the widths where the shell changes
and at ordinary intermediate widths, and asserts the measure the identity,
portrait and prose need rather than a particular set of tracks.
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

# 17rem: the identity column the atlas composition has at a wide desktop.
# Below it a name, a subtitle or a body break into one or two words a line.
# The requirement is in rem, so it grows with the reader's default text size
# instead of holding a pixel constant only true at 16px.
IDENTITY_MEASURE_REM = 17
LONG_TITLE = "Il lungo inverno dei corvi sul guado settentrionale e i patti mai scritti"
# 320 and 390 are phones, 699/700/701 the width where the head used to stack
# at a viewport breakpoint, 899/900/901 the shell's rail transition, and the
# rest are ordinary intermediate widths up to a wide desktop.
WIDTHS = (320, 390, 699, 700, 701, 899, 900, 901, 1024, 1100, 1440)


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


def _character_props(links=None, *, heading=None, can_manage=True) -> dict:
    return {
        **_common(),
        "character": SimpleNamespace(
            id=uuid4(),
            name=heading or "Fiamma Rossa",
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
        "can_manage": can_manage,
        "animals": animal_options(),
        "tints": tint_options(),
        "links": links,
    }


def _npc_props(links=None, *, heading=None, can_manage=True) -> dict:
    return {
        **_common(),
        "npc": SimpleNamespace(
            id=uuid4(),
            name=heading or "La Marchesa",
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
        "can_manage": can_manage,
        "animals": animal_options(),
        "tints": tint_options(),
        "links": links,
    }


def _place_props(links=None, *, heading=None, can_manage=True) -> dict:
    return {
        **_common(),
        "place": SimpleNamespace(
            id=uuid4(),
            name=heading or "Radura della Grande Quercia",
            short_description="Dove il bosco si apre.",
            body="La quercia segna il centro del bosco.",
            tint="p1",
            shape="triangolo",
            image_url=None,
            locked=False,
            is_draft=False,
            version=1,
        ),
        "can_manage": can_manage,
        "shapes": shape_options(),
        "tints": tint_options(),
        "is_current": False,
        "links": links,
    }


def _story_props(*, sessions=None, links=None, heading=None, can_manage=True) -> dict:
    # A story without related material has neither sessions nor backlinks.
    sessions = bool(links) if sessions is None else sessions
    return {
        **_common(),
        "story": SimpleNamespace(
            id=uuid4(),
            title=heading or "L'inverno dei corvi",
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
        "can_manage": can_manage,
        "metadata": [],
        "links": links,
    }


def _session_props(links=None, *, heading=None, can_manage=True) -> dict:
    return {
        **_common(),
        "session": SimpleNamespace(
            id=uuid4(),
            title=heading or "Il pedaggio del Guado",
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
        "can_manage": can_manage,
        "metadata": [],
        "links": links,
    }


def _page_props(links=None, *, heading=None, can_manage=True) -> dict:
    return {
        **_common(),
        "page": SimpleNamespace(
            id=uuid4(),
            title=heading or "Le regole della Casa",
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
        "can_manage": can_manage,
        "metadata": [],
        "links": links,
    }


# The six document types. ``lone`` is the page's own answer to "no related
# material": Page detail always keeps its `Altre pagine` aside.
DOCUMENT_PAGES = [
    ("pages.characters.CharacterDetail", _character_props, True),
    ("pages.npcs.NpcDetail", _npc_props, True),
    ("pages.places.PlaceDetail", _place_props, True),
    ("pages.sessions.SessionDetail", _session_props, True),
    ("pages.stories.StoryDetail", _story_props, True),
    ("pages.pages.PageDetail", _page_props, False),
]

# The three pages that put a portrait beside the identity.
PORTRAIT_PAGES = DOCUMENT_PAGES[:3]


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


def _layout(page) -> dict:
    """The document grid, its head and its prose, with their geometry."""
    return page.evaluate(
        """() => {
            const rect = (el) => {
                if (!el) return null;
                const r = el.getBoundingClientRect();
                return {
                    x: r.x, y: r.y, width: r.width, height: r.height,
                    right: r.right, bottom: r.bottom,
                };
            };
            const grid = document.querySelector('.grid-document');
            const heading = document.querySelector('h1');
            const gridStyle = grid ? getComputedStyle(grid) : null;
            const tracks = gridStyle
                ? gridStyle.gridTemplateColumns.split(' ').map(parseFloat).filter(Number.isFinite)
                : [];
            const columnGap = gridStyle ? parseFloat(gridStyle.columnGap) || 0 : 0;
            return {
                scrollWidth: document.documentElement.scrollWidth,
                rootFontSize: parseFloat(
                    getComputedStyle(document.documentElement).fontSize
                ),
                children: grid ? grid.children.length : 0,
                gridWidth: grid ? grid.clientWidth : 0,
                trackTotal: tracks.length
                    ? tracks.reduce((sum, width) => sum + width, 0)
                        + columnGap * (tracks.length - 1)
                    : 0,
                main: rect(grid && grid.children[0]),
                aside: rect(grid && grid.children.length > 1 ? grid.children[1] : null),
                face: rect(document.querySelector('.document__face')),
                identity: rect(document.querySelector('.document__id')),
                prose: rect(document.querySelector('.document__page .prose, article .prose')),
                heading: rect(heading),
                headingOverflow: heading ? heading.scrollWidth - heading.clientWidth : 0,
            };
        }"""
    )


def _required_measure(layout: dict) -> float:
    """The identity's measure in pixels at the page's own text size."""
    return IDENTITY_MEASURE_REM * layout["rootFontSize"]


def _assert_document_measure(layout: dict, width: int) -> None:
    """No horizontal overflow and no column below the identity's measure."""
    assert layout["scrollWidth"] <= width, f"the page scrolls sideways at {width}px"
    assert layout["trackTotal"] <= layout["gridWidth"] + 1, (
        f"the tracks take {layout['trackTotal']:.0f}px of a "
        f"{layout['gridWidth']:.0f}px grid at {width}px"
    )

    required = _required_measure(layout)
    for name in ("main", "identity", "prose"):
        column = layout[name]
        if column is None:
            continue
        assert column["width"] >= required, (
            f"the {name} column is {column['width']:.0f}px of the "
            f"{required:.0f}px it needs at {layout['rootFontSize']:.0f}px text, "
            f"{width}px viewport"
        )


def _assert_columns_do_not_overlap(layout: dict) -> None:
    main, aside = layout["main"], layout["aside"]
    if aside is None:
        return

    beside = aside["x"] >= main["right"] - 1
    below = aside["y"] >= main["bottom"] - 1
    assert beside or below, "the aside overlaps the document"
    if below:
        assert abs(aside["x"] - main["x"]) < 2, "the stacked aside kept its column"
        assert abs(aside["width"] - main["width"]) < 2, (
            "the stacked aside is not full width"
        )


def _assert_portrait_and_identity_do_not_overlap(layout: dict) -> None:
    face, identity = layout["face"], layout["identity"]
    if face is None or identity is None:
        return

    if abs(face["y"] - identity["y"]) < 2:
        assert identity["x"] >= face["right"] - 1, "the identity overlaps the portrait"
    else:
        assert identity["y"] >= face["bottom"] - 1, "the identity overlaps the portrait"
        assert abs(identity["x"] - face["x"]) < 2, (
            "the stacked identity kept its column"
        )


def _assert_heading_fits(layout: dict) -> None:
    heading = layout["heading"]
    assert heading is not None, "the document has no main heading"
    assert layout["headingOverflow"] <= 1, "the title overflows its column"
    if layout["identity"] is not None:
        assert heading["right"] <= layout["identity"]["right"] + 1


@pytest.mark.parametrize("width", WIDTHS)
@pytest.mark.parametrize(("component_name", "props", "lone"), DOCUMENT_PAGES)
def test_every_document_type_keeps_its_measure(
    component, component_name, props, lone, width
):
    """With related material and a long title, at every width that matters."""
    page = component.mount(
        component_name, props=props(links=_backlinks(), heading=LONG_TITLE)
    )
    page.set_viewport_size({"width": width, "height": 900})
    layout = _layout(page)

    _assert_document_measure(layout, width)
    _assert_columns_do_not_overlap(layout)
    _assert_portrait_and_identity_do_not_overlap(layout)
    _assert_heading_fits(layout)


@pytest.mark.parametrize("width", WIDTHS)
@pytest.mark.parametrize(("component_name", "props", "lone"), DOCUMENT_PAGES)
def test_every_document_type_keeps_its_measure_without_related_material(
    component, component_name, props, lone, width
):
    page = component.mount(component_name, props=props(links=None, heading=LONG_TITLE))
    page.set_viewport_size({"width": width, "height": 900})
    layout = _layout(page)

    _assert_document_measure(layout, width)
    _assert_portrait_and_identity_do_not_overlap(layout)
    _assert_heading_fits(layout)
    if lone:
        assert layout["children"] == 1, (
            "a document without related material has an aside"
        )


@pytest.mark.parametrize("width", (320, 390))
@pytest.mark.parametrize(("component_name", "props", "lone"), DOCUMENT_PAGES)
def test_every_document_fits_a_narrow_page_with_larger_text(
    component, component_name, props, lone, width
):
    """A 150% default text size makes every rem track larger than the page.

    The stacked children span the tracks, so the tracks must be able to shrink
    below the aside's 16rem and its gap instead of overflowing the grid.
    """
    page = component.mount(
        component_name, props=props(links=_backlinks(), heading=LONG_TITLE)
    )
    page.set_viewport_size({"width": width, "height": 900})
    page.add_style_tag(content="html { font-size: 150%; }")
    layout = _layout(page)

    assert layout["scrollWidth"] <= width, "the page scrolls sideways"
    assert layout["trackTotal"] <= layout["gridWidth"] + 1, (
        f"the tracks take {layout['trackTotal']:.0f}px of a "
        f"{layout['gridWidth']:.0f}px grid at {width}px"
    )
    _assert_columns_do_not_overlap(layout)
    _assert_portrait_and_identity_do_not_overlap(layout)
    if layout["identity"] is not None:
        assert abs(layout["identity"]["width"] - layout["main"]["width"]) < 2, (
            "the identity does not take the whole stacked width"
        )


@pytest.mark.parametrize("width", (701, 901, 1024))
@pytest.mark.parametrize(("component_name", "props", "lone"), DOCUMENT_PAGES)
def test_every_document_keeps_its_measure_with_larger_text(
    component, component_name, props, lone, width
):
    """A 150% text size makes the 15rem portrait 360px wide.

    The head must stack on the width the document actually gets, not on a
    viewport rule: at 701, 901 and 1024 the portrait beside the identity left
    it 251, 175 and 296px — below the 17rem (408px) it needs at that size.
    """
    page = component.mount(
        component_name, props=props(links=_backlinks(), heading=LONG_TITLE)
    )
    page.set_viewport_size({"width": width, "height": 900})
    page.add_style_tag(content="html { font-size: 150%; }")
    layout = _layout(page)

    _assert_document_measure(layout, width)
    _assert_columns_do_not_overlap(layout)
    _assert_portrait_and_identity_do_not_overlap(layout)
    _assert_heading_fits(layout)


@pytest.mark.parametrize("width", (390, 901, 1440))
@pytest.mark.parametrize(("component_name", "props", "lone"), PORTRAIT_PAGES)
def test_the_read_only_document_keeps_its_measure(
    component, component_name, props, lone, width
):
    """The read-only portrait is a different box from the image editor."""
    page = component.mount(
        component_name,
        props=props(links=_backlinks(), heading=LONG_TITLE, can_manage=False),
    )
    page.set_viewport_size({"width": width, "height": 900})
    layout = _layout(page)

    _assert_document_measure(layout, width)
    _assert_portrait_and_identity_do_not_overlap(layout)
    _assert_heading_fits(layout)


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


def test_the_aside_stacks_on_both_sides_of_the_rail_transition(component):
    """899/900 have no rail, 901 brings it back and takes 276px from the page.

    The document reflows on the width it actually gets, so the aside is below
    the document on both sides of the shell's transition, and the identity
    keeps its measure there.
    """
    for width in (899, 900, 901):
        page = component.mount(
            "pages.characters.CharacterDetail",
            props=_character_props(links=_backlinks(), heading=LONG_TITLE),
        )
        page.set_viewport_size({"width": width, "height": 900})
        main, aside = _children(page)
        layout = _layout(page)

        assert aside["y"] >= main["y"] + main["height"] - 1, (
            f"the aside is beside the document at {width}px"
        )
        assert layout["identity"]["width"] >= _required_measure(layout), (
            f"the identity column is {layout['identity']['width']:.0f}px at {width}px"
        )


def test_the_aside_returns_beside_the_document_when_the_page_can_hold_it(component):
    page = component.mount(
        "pages.characters.CharacterDetail", props=_character_props(links=_backlinks())
    )
    page.set_viewport_size({"width": 1440, "height": 900})
    main, aside = _children(page)

    assert aside["x"] >= main["x"] + main["width"] - 1, "the aside did not return"
    assert aside["width"] < main["width"], "the aside took the document's width"


def test_every_detail_page_reflows_at_the_same_document_width(component):
    """One contract for the six pages, not one breakpoint per caller."""
    for component_name, props, _ in DOCUMENT_PAGES:
        page = component.mount(component_name, props=props(links=_backlinks()))

        page.set_viewport_size({"width": 901, "height": 900})
        main, aside = _children(page)
        assert aside["y"] >= main["y"] + main["height"] - 1, (
            f"{component_name} at 901px"
        )

        page.set_viewport_size({"width": 1440, "height": 900})
        main, aside = _children(page)
        assert aside["x"] >= main["x"] + main["width"] - 1, (
            f"{component_name} at 1440px"
        )
