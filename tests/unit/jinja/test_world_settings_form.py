"""The world settings page builds its forms from the shared components.

The members form used raw ``input.input`` and ``select.select`` next to a
``common.Button``, so the same control looked different from every other form
in the application and carried no visible label.
"""

from pathlib import Path
from types import SimpleNamespace

from backend.jinja import get_catalog
from backend.navigation import Crumb, Option

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
        "roles": [
            Option(value="player", label="Giocatore"),
            Option(value="master", label="Master"),
        ],
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


def test_the_members_form_is_built_from_the_shared_field() -> None:
    html = _render()

    assert '<span class="field-label">Email</span>' in html
    assert '<span class="field-label">Ruolo</span>' in html
    assert '<option value="player"' in html
    assert '<option value="master"' in html


def test_the_members_form_keeps_the_legacy_classes_out() -> None:
    html = _render()

    assert 'class="input"' not in html
    assert 'class="select"' not in html
    assert 'class="row-inline"' not in html


def test_the_role_options_come_from_the_view() -> None:
    html = _render(roles=[Option(value="master", label="Solo master")])

    assert '<option value="master"' in html
    assert "Solo master" in html
    assert '<option value="player"' not in html
