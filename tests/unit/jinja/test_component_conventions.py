"""Static conventions that every JinjaX component must keep.

These are cheap to state and easy to break, and a broken one only shows up when
a page actually renders — which the compile-only tests in
``tests/integration/jinja/test_templates_compile.py`` do not do. A component
whose arguments are read before ``{#def #}`` compiles fine and raises
``UndefinedError`` at render time.
"""

import pathlib
import re

import pytest

COMPONENTS = pathlib.Path(__file__).parents[3] / "src" / "frontend" / "components"
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
