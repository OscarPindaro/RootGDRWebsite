"""Static conventions that every JinjaX component must keep.

These are cheap to state and easy to break, and a broken one only shows up when
a page actually renders — which the compile-only tests in
``tests/integration/jinja/test_templates_compile.py`` do not do. A component
whose arguments are read before ``{#def #}`` compiles fine and raises
``UndefinedError`` at render time.

The second convention here is selector ownership: one reusable root selector has
one stylesheet. Two owners make appearance depend on cascade order and on which
assets happened to be collected, which is the seam F1 exists to close.
"""

import pathlib
import re
from collections.abc import Iterator

import pytest

REPO = pathlib.Path(__file__).parents[3]
COMPONENTS = REPO / "src" / "frontend" / "components"
MAIN_CSS = REPO / "src" / "frontend" / "static" / "css" / "main.css"

NAMES = sorted(
    p.relative_to(COMPONENTS).as_posix() for p in COMPONENTS.rglob("*.jinja")
)

# JinjaX finds the argument declaration with a line-anchored match, so a
# ``{#def #}`` in the middle of a line is not seen at all.
DEF = re.compile(r"^\{#def\b", re.MULTILINE)
SET = re.compile(r"^\{%-?\s*set\s", re.MULTILINE)


def test_there_are_components_to_check() -> None:
    assert NAMES


@pytest.mark.parametrize("name", NAMES)
def test_the_def_starts_a_line_and_precedes_any_set(name: str) -> None:
    source = (COMPONENTS / name).read_text(encoding="utf-8")

    declaration = DEF.search(source)
    if declaration is None:
        # A fragment without arguments (an htmx response, say) needs no def.
        return

    first_set = SET.search(source)
    assert first_set is None or first_set.start() > declaration.start(), (
        f"{name}: a {{% set %}} runs before {{#def #}}, "
        "so the arguments it reads are undefined"
    )


# --- Selector ownership -----------------------------------------------------

# Reusable roots that one stylesheet owns. ``btn`` is the Button component's
# root class; the codebase has no ``.button`` selector.
OWNED_ROOTS = ("btn", "card", "dialog", "field", "pill", "table")

# Roots that two stylesheets still own, with the pair of owners and the ticket
# that removes the losing rules. The test fails on a stale entry, so an
# exception cannot outlive its migration.
MIGRATION_ALLOWLIST: dict[str, tuple[str, tuple[str, str]]] = {
    "btn": (
        "F3",
        (
            "src/frontend/components/common/Button.css",
            "src/frontend/static/css/main.css",
        ),
    ),
    "card": (
        "F14",
        (
            "src/frontend/components/common/Card.css",
            "src/frontend/static/css/main.css",
        ),
    ),
    "field": (
        "F4",
        (
            "src/frontend/components/common/Field.css",
            "src/frontend/static/css/main.css",
        ),
    ),
    "pill": (
        "F3",
        (
            "src/frontend/components/common/Pill.css",
            "src/frontend/static/css/main.css",
        ),
    ),
}

COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
CLASS_TOKEN = re.compile(r"\.(-?[_a-zA-Z][\w-]*)")
COMBINATOR = re.compile(r"[ >+~]")
BLOCK_SUFFIX = re.compile(r"__|--")


def _rule_preludes(source: str) -> Iterator[str]:
    """Yield each rule's selector text, skipping at-rule preludes.

    Brace tracking is enough for these stylesheets: a nested rule inside
    ``@media`` is still a rule, and ``@keyframes`` steps match no class.
    """
    buffer: list[str] = []
    for character in source:
        if character == "{":
            prelude = "".join(buffer).strip()
            buffer = []
            if prelude and not prelude.startswith("@"):
                yield prelude
        elif character == "}":
            buffer = []
        else:
            buffer.append(character)


def _root_classes(selector: str) -> set[str]:
    """The classes of a selector's first compound, stripped of BEM suffixes.

    ``.card--npc .card__name`` belongs to root ``card``; ``html[data-x] .btn``
    belongs to no class root at all, because its first compound has none.
    """
    head = COMBINATOR.split(selector.strip(), 1)[0]
    return {
        BLOCK_SUFFIX.split(name, maxsplit=1)[0] for name in CLASS_TOKEN.findall(head)
    }


def _owns(stylesheet: pathlib.Path, root: str) -> bool:
    source = COMMENT.sub("", stylesheet.read_text(encoding="utf-8"))
    return any(
        root in _root_classes(selector)
        for prelude in _rule_preludes(source)
        for selector in prelude.split(",")
    )


def _owners(root: str) -> list[str]:
    return sorted(
        stylesheet.relative_to(REPO).as_posix()
        for stylesheet in [MAIN_CSS, *sorted(COMPONENTS.rglob("*.css"))]
        if _owns(stylesheet, root)
    )


@pytest.mark.parametrize("root", OWNED_ROOTS)
def test_a_reusable_root_selector_has_one_owner(root: str) -> None:
    owners = _owners(root)
    allowed = MIGRATION_ALLOWLIST.get(root)

    if allowed:
        ticket, expected = allowed
        assert owners == sorted(expected), (
            f".{root} is allowlisted for {ticket} as {sorted(expected)} but is "
            f"now owned by {owners}. Remove the MIGRATION_ALLOWLIST entry or "
            "restore the single owner."
        )
        return

    assert len(owners) <= 1, (
        f".{root} is owned by {owners}. One root selector gets one stylesheet: "
        "give the domain component a domain name, or delete the losing rules."
    )
