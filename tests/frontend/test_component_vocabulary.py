"""The bounded component vocabulary recorded by REQ-0019/T18.

The owner decision lives in ``docs/features-implemented/component-vocabulary.md``.
These assertions keep that document, the component templates, their stylesheets
and the design kit on the same finite list.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from backend.jinja import get_catalog

pytestmark = pytest.mark.frontend

COMPONENTS = Path(__file__).parents[2] / "src" / "frontend" / "components"
MAIN_CSS = COMPONENTS.parent / "static" / "css" / "main.css"
MANUAL = (
    Path(__file__).parents[2]
    / "docs"
    / "features-implemented"
    / "component-vocabulary.md"
)
SHOWCASE = COMPONENTS / "pages" / "showcase" / "Showcase.jinja"

BUTTON_CSS = COMPONENTS / "common" / "Button.css"
BUTTON_JINJA = COMPONENTS / "common" / "Button.jinja"
PILL_CSS = COMPONENTS / "common" / "Pill.css"
GRID_CSS = COMPONENTS / "common" / "Grid.css"
GRID_JINJA = COMPONENTS / "common" / "Grid.jinja"
DOCUMENT_CSS = COMPONENTS / "editorial" / "Document.css"

# Classes Button.css defines that are not variants: the root, its layout and
# state markers, and the size rules.
BUTTON_NON_VARIANTS = {
    "icon",
    "label",
    "icon-only",
    "mixed",
    "block",
    "toggle",
    "selected",
    "xs",
    "sm",
    "md",
    "lg",
    "xl",
}


def _documented() -> dict[str, list[str]]:
    text = MANUAL.read_text(encoding="utf-8")
    block = text.split("<!-- component-vocabulary:start -->", 1)[1].split(
        "<!-- component-vocabulary:end -->", 1
    )[0]
    documented: dict[str, list[str]] = {}
    for line in block.splitlines():
        match = re.match(r"^([a-z.-]+):\s*(.+?)\s*$", line)
        if match:
            documented[match.group(1)] = match.group(2).split()
    return documented


def _classes(stylesheet: Path) -> set[str]:
    css = re.sub(r"/\*.*?\*/", "", stylesheet.read_text(encoding="utf-8"), flags=re.S)
    return set(re.findall(r"\.([a-z][a-z0-9-]*)", css))


def _render(name: str, **props: object) -> str:
    return str(
        get_catalog(str(COMPONENTS), app_name="Root GDR").render(
            name, content="x", **props
        )
    )


def _button_tags(text: str) -> list[str]:
    return re.findall(r"<common\.Button\b([^>]*)>", text, flags=re.S)


def test_button_sets_match_the_stylesheet_template_and_design_kit() -> None:
    documented = _documented()
    classes = _classes(BUTTON_CSS)
    styled_variants = {
        name.removeprefix("btn-") for name in classes if name.startswith("btn-")
    } - BUTTON_NON_VARIANTS
    styled_sizes = {name.removeprefix("btn-") for name in classes} & {
        "xs",
        "sm",
        "md",
        "lg",
        "xl",
    }

    assert set(documented["button.variant"]) == styled_variants
    assert set(documented["button.size"]) == {"xs", "sm", "md"}
    assert set(documented["button.size.experimental"]) == {"lg", "xl"}
    assert (
        set(documented["button.size"]) | set(documented["button.size.experimental"])
        == styled_sizes
    )

    for variant in documented["button.variant"]:
        assert f"btn-{variant}" in _render("common.Button", variant=variant)
    for size in documented["button.size"] + documented["button.size.experimental"]:
        assert f"btn-{size}" in _render("common.Button", size=size)

    assert 'shape="round"' in BUTTON_JINJA.read_text(encoding="utf-8").splitlines()[0]
    reserved_shapes = set(documented["button.shape.reserved-noop"])
    assert reserved_shapes == {"round", "square"}
    for shape in reserved_shapes:
        assert f"btn-{shape}" in _render("common.Button", shape=shape)

    all_component_classes = set().union(
        *(_classes(stylesheet) for stylesheet in COMPONENTS.rglob("*.css"))
    )
    assert not {f"btn-{shape}" for shape in reserved_shapes} & all_component_classes


def test_pill_set_matches_the_stylesheet_and_template() -> None:
    documented = set(_documented()["pill.variant"])
    styled = {
        name.removeprefix("pill-")
        for name in _classes(PILL_CSS)
        if name.startswith("pill-")
    }

    assert documented == styled
    for variant in documented:
        assert f'class="pill pill-{variant}"' in _render("common.Pill", variant=variant)


def test_grid_sets_match_the_stylesheet_tokens_and_template() -> None:
    documented = _documented()
    styled_columns = {
        name.removeprefix("grid-columns-")
        for name in _classes(GRID_CSS)
        if name.startswith("grid-columns-")
    }
    main_css = MAIN_CSS.read_text(encoding="utf-8")
    spacing_steps = set(re.findall(r"--sp-(\d+)\s*:", main_css))
    minimums = set(re.findall(r"--grid-min-([a-z]+)\s*:", main_css))

    assert set(documented["grid.columns"]) == styled_columns
    assert set(documented["grid.gap"]) == spacing_steps
    assert set(documented["grid.min"]) == minimums

    for columns in documented["grid.columns"]:
        assert f"grid-columns-{columns}" in _render("common.Grid", columns=columns)
    for gap in documented["grid.gap"]:
        assert f"--grid-gap: var(--sp-{gap});" in _render("common.Grid", gap=gap)
    for minimum in documented["grid.min"]:
        assert f"--grid-min: var(--grid-min-{minimum});" in _render(
            "common.Grid", min=minimum
        )

    def_line = GRID_JINJA.read_text(encoding="utf-8").splitlines()[0]
    for flag in documented["grid.flags"]:
        assert f"{flag}=False" in def_line
        assert f"grid-{flag}" in _render("common.Grid", **{flag: True})
    assert "grid-document" in _classes(DOCUMENT_CSS)


def test_callers_use_only_documented_options() -> None:
    documented = _documented()
    supported_sizes = set(documented["button.size"])
    experimental_sizes = set(documented["button.size.experimental"])
    showcase = SHOWCASE.read_text(encoding="utf-8")

    grid_columns: set[str] = set()
    for tag in re.findall(r"<common\.Grid\b([^>]*)>", showcase):
        grid_columns.update(re.findall(r"(?<![:\w-])columns=(\d+)", tag))
    assert grid_columns <= set(documented["grid.columns"])

    choice_columns: set[str] = set()
    for tag in re.findall(r"<common\.ChoiceGrid\b([^>]*)>", showcase):
        choice_columns.update(re.findall(r'columns="(\d+)"', tag))
    assert choice_columns - set(documented["grid.columns"]), (
        "ChoiceGrid's 6/8 columns are its own --columns density, not Grid columns"
    )

    for literal in re.findall(r"\{% for group_size in (\[[^\]]*\]) %\}", showcase):
        assert set(ast.literal_eval(literal)) <= supported_sizes | experimental_sizes

    for template in COMPONENTS.rglob("*.jinja"):
        text = template.read_text(encoding="utf-8")
        for tag in _button_tags(text):
            assert set(re.findall(r'(?<![:\w-])variant="([a-z-]+)"', tag)) <= set(
                documented["button.variant"]
            ), template
            sizes = set(re.findall(r'(?<![:\w-])size="([a-z]+)"', tag))
            assert sizes <= supported_sizes | experimental_sizes, template
            if template != SHOWCASE:
                assert sizes <= supported_sizes, template
        for component in ("IconButton", "ButtonGroup"):
            for tag in re.findall(rf"<common\.{component}\b([^>]*)>", text, re.S):
                assert (
                    set(re.findall(r'(?<![:\w-])size="([a-z]+)"', tag))
                    <= supported_sizes
                ), template
        for tag in re.findall(r"<common\.Pill\b([^>]*)>", text, re.S):
            assert set(re.findall(r'(?<![:\w-])variant="([a-z-]+)"', tag)) <= set(
                documented["pill.variant"]
            ), template


def test_unsupported_values_are_unstyled_until_t19_rejects_them() -> None:
    documented = _documented()

    assert "btn-ghost" in _render("common.Button", variant="ghost")
    assert "btn-ghost" not in _classes(BUTTON_CSS)

    assert "pill-ghost" in _render("common.Pill", variant="ghost")
    assert "pill-ghost" not in _classes(PILL_CSS)

    assert "grid-columns-4" in _render("common.Grid", columns=4)
    assert "grid-columns-4" not in _classes(GRID_CSS)

    assert "--grid-gap: var(--sp-7);" in _render("common.Grid", gap=7)
    assert "7" not in documented["grid.gap"]

    assert "--grid-min: var(--grid-min-huge);" in _render("common.Grid", min="huge")
    assert "huge" not in documented["grid.min"]
