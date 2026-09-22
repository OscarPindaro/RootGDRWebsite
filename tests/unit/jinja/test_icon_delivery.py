"""Icon and font delivery (F20).

A reading page must download no Lucide runtime, and an htmx swap must need no
icon pass: every icon is an inline `<svg>` the server already rendered. The
typography must be self-hosted, so it survives an unavailable external network.

These render the real components with the real catalog; no browser is needed to
see that the markup carries the whole icon and that the head names no font host.
"""

import re
from pathlib import Path
from types import SimpleNamespace

from backend.jinja import get_catalog
from backend.navigation import Crumb

REPO = Path(__file__).parents[3]
COMPONENTS_DIR = REPO / "src" / "frontend" / "components"
MAIN_CSS = REPO / "src" / "frontend" / "static" / "css" / "main.css"
FONT_HOSTS = ("fonts.googleapis.com", "fonts.gstatic.com")

# A Lucide placeholder or a runtime reference, in any casing.
LUCIDE = re.compile(r"lucide", re.IGNORECASE)
SVG = re.compile(r"<svg\b[^>]*class=\"icon icon--[a-z0-9]+\"[^>]*>")
FONT_FACE = re.compile(r"@font-face\s*\{(.*?)\}", re.DOTALL)


def _catalog():
    return get_catalog(str(COMPONENTS_DIR), app_name="Root GDR")


def _user(role: str = "admin") -> SimpleNamespace:
    return SimpleNamespace(
        name="Ada",
        email="ada@example.com",
        role=role,
        avatar_url=None,
        symbol_style="icons",
    )


def _reading_page() -> str:
    """A detail page that renders a full document: head, shell and many icons."""
    world = SimpleNamespace(
        id="01a0c000-0000-7000-8000-000000000001",
        name="Il Boschetto di Smeraldo",
        description="Un bosco di frontiera.",
        version=1,
        image_url=None,
        created_by=SimpleNamespace(id="01a0c000-0000-7000-8000-000000000002"),
    )
    return str(
        _catalog().render(
            "pages.worlds.WorldSettings",
            world=world,
            members=[],
            invites=[],
            world_context=None,
            nav=None,
            pages=None,
            crumbs=[Crumb(label="Mondi", href="/worlds")],
            description_html="<p>Un bosco di frontiera.</p>",
            current_user=_user(),
        )
    )


def _fragment() -> str:
    """An htmx fragment: it never passes through BlankPage."""
    return str(_catalog().render("pages.admin.InviteDialog", roles=[]))


def test_a_reading_page_carries_no_lucide_runtime() -> None:
    html = _reading_page()

    assert LUCIDE.search(html) is None, "a reading page still references Lucide"
    assert "data-lucide" not in html


def test_every_icon_on_a_reading_page_is_rendered_on_the_server() -> None:
    html = _reading_page()
    icons = SVG.findall(html)

    assert icons, "the page should render icons"
    # Every one is a complete svg whose strokes take the surrounding colour.
    for icon in icons:
        assert 'stroke="currentColor"' in icon
        assert 'viewBox="0 0 24 24"' in icon
        assert "style=" not in icon, f"icon carries a pixel style: {icon}"


def test_an_htmx_fragment_needs_no_icon_pass() -> None:
    """The swapped markup already contains the icons, so no createIcons() runs."""
    html = _fragment()

    assert LUCIDE.search(html) is None
    assert SVG.findall(html), "the fragment should carry its icons already"


def test_the_fragment_declares_the_icon_stylesheet() -> None:
    """An htmx fragment carries only what its ``{#css #}`` directive names."""
    source = (COMPONENTS_DIR / "pages" / "admin" / "InviteDialog.jinja").read_text(
        encoding="utf-8"
    )

    assert "common/Icon.css" in source


def test_the_head_names_no_external_font_host() -> None:
    html = _reading_page()

    for host in FONT_HOSTS:
        assert host not in html, f"the head still reaches {host}"


def test_the_head_preloads_only_the_two_regular_faces() -> None:
    html = _reading_page()
    preloads = re.findall(r'<link rel="preload"[^>]*as="font"[^>]*>', html)

    assert len(preloads) == 2, preloads
    assert any("newsreader-latin-var.woff2" in tag for tag in preloads)
    assert any("ibm-plex-sans-latin-var.woff2" in tag for tag in preloads)
    for tag in preloads:
        assert 'type="font/woff2"' in tag
        assert "crossorigin" in tag


def test_the_stylesheet_declares_only_self_hosted_faces() -> None:
    css = MAIN_CSS.read_text(encoding="utf-8")
    faces = FONT_FACE.findall(css)

    assert faces, "main.css declares no @font-face"
    for face in faces:
        assert "font-display: swap" in face
        src = re.search(r"src:\s*url\(([^)]*)\)", face)
        assert src is not None
        assert src.group(1).startswith('"/static/fonts/'), src.group(1)


def test_the_documented_fallback_stacks_are_preserved() -> None:
    css = MAIN_CSS.read_text(encoding="utf-8")

    assert '--serif: "Newsreader", "Iowan Old Style", Georgia, serif;' in css
    assert '--sans: "IBM Plex Sans", system-ui, -apple-system, sans-serif;' in css
    assert '--mono: "IBM Plex Mono", ui-monospace, "SFMono-Regular", monospace;' in css
