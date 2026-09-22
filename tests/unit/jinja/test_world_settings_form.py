"""The world settings page owns no inline membership form.

The old section exposed a raw email/role form and listed members as prose
links. F9 replaced both with a page-domain table and a dialog; this test pins
the page contract: the Giocatori heading, the plus that opens the dialog, and
the absence of the legacy inline form.
"""

from pathlib import Path
from types import SimpleNamespace

from backend.jinja import get_catalog
from backend.navigation import Crumb

COMPONENTS_DIR = Path(__file__).parents[3] / "src" / "frontend" / "components"


def _catalog():
    return get_catalog(str(COMPONENTS_DIR), app_name="Root GDR")


def _render(**overrides):
    world = SimpleNamespace(
        id="01a0c000-0000-7000-8000-000000000001",
        name="Il Boschetto di Smeraldo",
        description="Un bosco di frontiera.",
        version=1,
        image_url=None,
        created_by=SimpleNamespace(id="01a0c000-0000-7000-8000-000000000002"),
    )
    props = {
        "world": world,
        "members": [],
        "invites": [],
        "world_context": None,
        "nav": None,
        "pages": None,
        "crumbs": [Crumb(label="Mondi", href="/worlds")],
        "description_html": "<p>Un bosco di frontiera.</p>",
        "current_user": SimpleNamespace(
            name="Ada",
            email="ada@example.com",
            role="admin",
            avatar_url=None,
            symbol_style="icons",
        ),
    }
    props.update(overrides)
    return str(_catalog().render("pages.worlds.WorldSettings", **props))


def test_the_access_section_is_titled_giocatori() -> None:
    html = _render()

    assert ">Giocatori</h2>" in html
    assert ">Membri</h2>" not in html


def test_the_section_offers_the_dialog_through_a_plus_icon_button() -> None:
    html = _render()

    assert 'data-testid="world-member-add"' in html
    assert 'data-icon="plus"' in html
    assert 'hx-target="#world-member-dialog"' in html


def test_no_inline_add_form_remains_on_the_page() -> None:
    html = _render()

    # The form lived here with raw input/select classes and a submit button.
    assert 'class="input"' not in html
    assert 'class="select"' not in html
    assert 'class="row-inline"' not in html
    assert 'data-testid="add-world-member"' not in html
    assert 'name="email"' not in html
    assert 'name="role"' not in html


def test_the_members_are_rendered_by_the_table_component() -> None:
    html = _render()

    assert 'id="world-members"' in html
    assert 'class="table"' in html
    assert ">Persona</th>" in html
    assert ">Stato</th>" in html
