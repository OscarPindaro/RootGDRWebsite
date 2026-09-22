"""The server-side icon registry (F20).

Icons used to be `<i data-lucide>` placeholders that the Lucide runtime replaced
in the browser, so a typo rendered nothing and an htmx swap needed a second pass.
They are now rendered on the server from a registry generated out of the pinned
Lucide package. This file pins the two halves of that promise: every name the
application actually uses is in the registry, and a name that is not fails loudly
instead of disappearing.
"""

import json
import re
from pathlib import Path

import pytest

from backend.icons import ICONS, SIZE_CLASSES, UnknownIcon, icon_body, icon_class

REPO = Path(__file__).parents[2]
COMPONENTS = REPO / "src" / "frontend" / "components"
BACKEND = REPO / "src" / "backend"
PACKAGE_JSON = REPO / "package.json"
REGISTRY = BACKEND / "icons.py"

# `icon="plus"` / `confirm_icon="trash-2"` on any component. The negative
# lookbehind keeps `:icon` (a dynamic prop) out of the static branch.
STATIC_ICON = re.compile(r'(?<![:\w])(?:icon|confirm_icon)\s*=\s*"([^"]*)"')
# `:icon="'lock' if locked else 'lock-open'"` — a dynamic prop whose branches are
# the names; the string literals inside are what must resolve.
DYNAMIC_ICON = re.compile(r':(?:icon|confirm_icon)\s*=\s*"([^"]*)"')
# `<common.Icon name="x" />` — the same contract, on the component itself.
ICON_NAME = re.compile(r"<common\.Icon\b[^>]*?(?<![:\w])name\s*=\s*\"([^\"]*)\"")
LITERAL = re.compile(r"'([^']*)'|\"([^\"]*)\"")

# A registry entry that is not used anywhere is dead weight; the inventory is the
# union of what the templates and the views pass.
INVENTORY = (
    COMPONENTS,
    BACKEND,
)


def _used_icon_names() -> set[str]:
    names: set[str] = set()
    for folder in INVENTORY:
        for path in sorted(folder.rglob("*.jinja")) + sorted(folder.rglob("*.py")):
            text = path.read_text(encoding="utf-8")
            names.update(match.group(1) for match in STATIC_ICON.finditer(text))
            for match in DYNAMIC_ICON.finditer(text):
                names.update(
                    first or second for first, second in LITERAL.findall(match.group(1))
                )
            names.update(match.group(1) for match in ICON_NAME.finditer(text))
    names.discard("")
    return names


def test_every_icon_the_application_uses_is_in_the_registry() -> None:
    """A typo — or a new icon nobody generated — fails here, not at render time."""
    used = _used_icon_names()
    missing = sorted(used - ICONS.keys())
    assert missing == [], (
        f"icons used but not generated: {missing}. "
        "Add them to tools/build_icons.mjs and run `npm run icons`."
    )


def test_the_registry_has_no_unused_entry() -> None:
    unused = sorted(ICONS.keys() - _used_icon_names())
    assert unused == [], f"registry entries with no caller: {unused}"


def test_every_registry_entry_is_lucide_markup() -> None:
    for name, body in ICONS.items():
        assert body.strip(), name
        # Lucide icons are strokes. A fill is allowed only when it is the
        # surrounding colour, or the icon would stop inheriting it.
        assert 'fill="#' not in body, name
        assert body.startswith("<") and body.endswith(">"), name


def test_an_unknown_name_raises_instead_of_rendering_nothing() -> None:
    with pytest.raises(UnknownIcon):
        icon_body("not-a-lucide-icon")


def test_an_unknown_size_raises() -> None:
    with pytest.raises(UnknownIcon):
        icon_class(17)


def test_a_size_becomes_a_class_not_a_pixel_style() -> None:
    assert icon_class(24) == "icon icon--lg"
    assert icon_class("24") == "icon icon--lg"
    assert set(SIZE_CLASSES) == {16, 18, 20, 24, 32, 40, 48}


def test_the_registry_is_pinned_to_the_generated_lucide_version() -> None:
    """The registry is reproducible: the pin, the header and the source agree."""
    pin = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))["devDependencies"][
        "lucide"
    ]
    assert re.fullmatch(r"\d+\.\d+\.\d+", pin), (
        f"lucide is pinned as {pin!r}: a floating range would let the registry "
        "drift from what it was generated from"
    )
    header = REGISTRY.read_text(encoding="utf-8")
    assert f"lucide@{pin}" in header
    assert "ISC" in header
    assert (BACKEND / "icons.LICENSE").is_file()
