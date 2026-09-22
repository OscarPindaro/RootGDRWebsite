"""Visible labels on identity fields (world settings and document editors).

The fields used to carry no label ("Identità" as a vague section title, no
"Name"/"Title" over the editable headings) and "Descrizione Markdown" told the
author nothing useful.
"""

from pathlib import Path
from types import SimpleNamespace

from backend.content.view_helpers import animal_options, tint_options
from backend.jinja import get_catalog

COMPONENTS_DIR = Path(__file__).parents[3] / "src" / "frontend" / "components"

WORLD_ID = "11111111-1111-1111-1111-111111111111"
OWNER_ID = "22222222-2222-2222-2222-222222222222"


def _catalog():
    return get_catalog(str(COMPONENTS_DIR), app_name="Root GDR")


def _user() -> SimpleNamespace:
    return SimpleNamespace(
        name="Ada",
        email="ada@example.com",
        role="member",
        avatar_url=None,
        symbol_style="icons",
    )


def _world() -> SimpleNamespace:
    return SimpleNamespace(
        id=WORLD_ID,
        name="Bosco",
        description="d",
        version=1,
        image_url=None,
        created_by=SimpleNamespace(id=OWNER_ID),
    )


def _context(world) -> SimpleNamespace:
    return SimpleNamespace(id=str(world.id), name=world.name, role="Master")


def test_world_settings_labels_the_fields_and_drops_the_section_title() -> None:
    world = _world()
    html = str(
        _catalog().render(
            "pages.worlds.WorldSettings",
            world=world,
            members=[
                SimpleNamespace(
                    user=SimpleNamespace(
                        id=OWNER_ID,
                        name="Ada",
                        email="ada@example.com",
                        avatar_url=None,
                    ),
                    role="master",
                )
            ],
            world_context=_context(world),
            nav=[],
            crumbs=[],
            description_html="<p>x</p>",
            pages=[],
            current_user=_user(),
        )
    )

    assert '<span class="eyebrow">Nome</span>' in html
    assert '<span class="eyebrow">Descrizione</span>' in html
    assert "Descrizione Markdown" not in html
    assert "Identità" not in html


def test_character_document_labels_name_and_title() -> None:
    world = _world()
    character = SimpleNamespace(
        id="33333333-3333-3333-3333-333333333333",
        name="Rugginosa",
        title="La Senza Tana",
        short_description="gatta",
        body="testo",
        version=1,
        locked=False,
        image_url=None,
        tint="p1",
        animal="🐈",
        is_draft=False,
        owner=SimpleNamespace(name="Ada"),
    )
    html = str(
        _catalog().render(
            "pages.characters.CharacterDetail",
            world=world,
            world_context=_context(world),
            nav=[],
            character=character,
            can_manage=True,
            crumbs=[],
            animals=animal_options(),
            tints=tint_options(),
            pages=[],
            short_html="<p>gatta</p>",
            body_html="<p>testo</p>",
            links=None,
            current_user=_user(),
            auto_edit=False,
        )
    )

    assert html.count('<span class="eyebrow">Nome</span>') == 1
    assert html.count('<span class="eyebrow">Titolo</span>') == 1
