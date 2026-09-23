"""The transition is over: no production file may name a retired selector.

Each name below is one an earlier ticket replaced. The scan is deliberately a
source check rather than a style check: a legacy class that survives in a
template is invisible until someone reads the markup, and it is exactly what
lets a second visual system creep back in.

Comments are stripped first, so a file may still *name* what it replaced while
explaining it. The companion assertion at the bottom is the same "one API, no
compatibility layer" rule applied to the component rather than the stylesheet:
every ``common.Button`` variant the product ships has a rule, and no variant
exists that no page calls.
"""

from __future__ import annotations

import pathlib
import re

import pytest

REPO = pathlib.Path(__file__).parents[3]
COMPONENTS = REPO / "src" / "frontend" / "components"
SCRIPTS = REPO / "src" / "frontend" / "js"
BUTTON_CSS = COMPONENTS / "common" / "Button.css"

# Retired by: F2 .docpage/.article, F3 .btn--text and the double-dash pills,
# F4 .field__bar/.field-label, F5/F9/F10 hx-confirm, F6 the image reload,
# F10 .docbar__lead/__actions, F13 .cover--new, F14 .card__*/.card--npc,
# F16 the class-shown palette, F20 the Lucide runtime, F21 .grid--quick.
LEGACY = {
    r"\.btn--text\b": "F3 replaced it with .btn-text",
    r"\.pill--[a-z]": "F3 made common.Pill emit single-dash variants",
    r"\.card__(media|body|name|title|owner|faction|monogram)": (
        "F14 renamed the entity card root to .entity-card"
    ),
    r"\.card--npc": "F14 renamed it to .entity-card--npc",
    r"\.docpage\b": "F2 replaced it with common.Grid document",
    r"\.article\b": "F2 replaced it with common.Grid document",
    r"\.field__bar\b": "F4 removed it",
    r"\.field-label\b": "F4 renamed it to .field__label",
    r"\.field__hint\b": "F4 renamed it to .hint",
    r"\.grid--quick\b": "F21 pointed the landmark at .grid-flush",
    r"\.grid--two\b": "F14 removed it",
    r"\.cover--new\b": "F13 deleted the dead block",
    r"\.docbar__(lead|actions)\b": "F10 split the bar into __status and __commands",
    r"data-lucide": "F20 renders icons on the server",
    r"createIcons": "F20 removed the runtime pass",
    r"lucide": "F20 removed the runtime",
    r"hx-confirm": "F5/F9/F10 confirm through the shared dialog",
    r"palette\.is-open": "F16 made the palette a native dialog, not a shown div",
}

# The image flow no longer reloads (F6). The editor's conflict recovery still
# does, deliberately, so that one is checked in the components only.
COMPONENT_ONLY = {r"location\.reload": "F6 removed the reload-driven image flow"}

COMMENT = re.compile(r"(?m)\{#.*?#\}|/\*.*?\*/|^\s*//.*$", re.DOTALL)


def _sources(root: pathlib.Path, suffixes: tuple[str, ...]) -> list[pathlib.Path]:
    return sorted(
        path
        for suffix in suffixes
        for path in root.rglob(f"*{suffix}")
        if "node_modules" not in path.parts
    )


def _scan(pattern: str, files: list[pathlib.Path]) -> list[str]:
    retired = re.compile(pattern)
    return [
        f"{path.relative_to(REPO)}:{number}"
        for path in files
        for number, line in enumerate(
            COMMENT.sub("", path.read_text(encoding="utf-8")).splitlines(), 1
        )
        if retired.search(line)
    ]


@pytest.mark.parametrize("pattern", sorted({**LEGACY, **COMPONENT_ONLY}))
def test_no_production_file_names_a_retired_selector(pattern: str) -> None:
    where = {**LEGACY, **COMPONENT_ONLY}[pattern]
    files = _sources(COMPONENTS, (".jinja", ".js"))
    if pattern not in COMPONENT_ONLY:
        files += _sources(SCRIPTS, (".js",))

    found = _scan(pattern, files)

    assert not found, f"{pattern} is retired — {where}: {found}"


def test_the_button_variants_the_css_defines_are_the_ones_the_product_uses() -> None:
    """One component API: a variant exists because a page calls it."""
    defined = set(
        re.findall(r"^\.btn-([a-z]+)\b", BUTTON_CSS.read_text(), re.MULTILINE)
    )
    # Sizes, shapes and layout modifiers share the prefix but are not variants.
    modifiers = {
        "xs",
        "sm",
        "md",
        "lg",
        "xl",
        "round",
        "square",
        "block",
        "icon",
        "mixed",
        "toggle",
        "selected",
        "busy",
    }
    variants = defined - modifiers

    called = set()
    for path in _sources(COMPONENTS, (".jinja",)):
        for invocation in re.finditer(
            r"<common\.Button\b(.*?)/?>", path.read_text(encoding="utf-8"), re.S
        ):
            # A leading colon is a bound expression, not a literal variant.
            match = re.search(r'(?<!:)variant="([a-z]+)"', invocation.group(1))
            called.add(match.group(1) if match else "primary")

    assert variants == called, (
        f"Button.css defines {sorted(variants)} but production calls {sorted(called)}"
    )
