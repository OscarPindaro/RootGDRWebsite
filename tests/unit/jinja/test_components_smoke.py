"""Runtime smoke tests for components.

Template compilation only checks syntax; it does not catch an undefined Jinja
global (e.g. a renamed ``shape`` helper) or a missing component argument. These
render the showcase and the small shared components for real.
"""

from pathlib import Path
from types import SimpleNamespace

from backend.content.view_helpers import animal_options, shape_options, tint_options
from backend.jinja import get_catalog

COMPONENTS_DIR = Path(__file__).parents[3] / "src" / "frontend" / "components"


def _catalog():
    return get_catalog(str(COMPONENTS_DIR), app_name="Root GDR")


def _showcase(**extra):
    return str(
        _catalog().render(
            "pages.showcase.Showcase",
            animals=animal_options(),
            tints=tint_options(),
            shapes=shape_options(),
            **extra,
        )
    )


def test_showcase_renders_every_section() -> None:
    """The showcase is the living spec; if it 500s, the design system is broken."""
    html = _showcase(users=[])
    assert "Design Kit" in html
    assert "Role marks" in html
    assert "Shapes" in html
    assert "Choice grids" in html


def test_showcase_renders_with_a_signed_in_user() -> None:
    user = SimpleNamespace(
        name="Admin",
        email="admin@example.com",
        role="admin",
        avatar_url=None,
        symbol_style="shapes",
    )
    html = _showcase(users=[], current_user=user)
    assert "Design Kit" in html


def test_mark_and_shape_components_render_svg() -> None:
    catalog = _catalog()
    mark = str(catalog.render("common.Mark", role="luoghi"))
    shape = str(catalog.render("common.Shape", name="rombo"))
    assert "<svg" in mark
    assert "<svg" in shape
    assert "<polygon" in shape
