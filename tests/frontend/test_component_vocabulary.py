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

from backend.jinja import ComponentOptionError, get_catalog

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


def _audit() -> dict[str, list[str]]:
    text = MANUAL.read_text(encoding="utf-8")
    block = text.split("<!-- component-vocabulary-audit:start -->", 1)[1].split(
        "<!-- component-vocabulary-audit:end -->", 1
    )[0]
    audit: dict[str, list[str]] = {}
    for line in block.splitlines():
        match = re.match(r"^([a-z.-]+):\s*(.+?)\s*$", line)
        if match:
            audit[match.group(1)] = match.group(2).split()
    return audit


def _classes(stylesheet: Path) -> set[str]:
    css = re.sub(r"/\*.*?\*/", "", stylesheet.read_text(encoding="utf-8"), flags=re.S)
    return set(re.findall(r"\.([a-z][a-z0-9-]*)", css))


def _templates() -> dict[Path, str]:
    return {
        template: template.read_text(encoding="utf-8")
        for template in COMPONENTS.rglob("*.jinja")
    }


def _literal(tag: str, attribute: str) -> set[str]:
    return set(re.findall(rf'(?<![:\w-]){attribute}="([a-z0-9-]+)"', tag))


def _loop_sizes(source: str) -> set[str]:
    sizes: set[str] = set()
    for variable, literal, body in re.findall(
        r"\{% for (\w+) in (\[[^\]]*\]) %\}(.*?)\{% endfor %\}", source, re.S
    ):
        if f':size="{variable}"' in body:
            sizes.update(ast.literal_eval(literal))
    return sizes


def _pill_variants(source: str) -> set[str]:
    variants: set[str] = set()
    for tag in re.findall(r"<common\.Pill\b([^>]*)>", source, re.S):
        variants |= _literal(tag, "variant") or {"neutral"}
    return variants


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


def test_documented_options_have_a_consumer_or_a_recorded_retention() -> None:
    documented = _documented()
    audit = _audit()
    templates = _templates()

    button_variants: set[str] = set()
    button_sizes: set[str] = set()
    pill_variants: set[str] = set()
    grid_columns: set[str] = set()
    grid_minimums: set[str] = set()
    grid_flags: set[str] = set()

    for source in templates.values():
        for tag in _button_tags(source):
            button_variants |= _literal(tag, "variant")
            button_sizes |= _literal(tag, "size")
        button_sizes |= _loop_sizes(source)
        pill_variants |= _pill_variants(source)
        for tag in re.findall(r"<common\.Grid\b([^>]*)>", source, re.S):
            grid_columns |= set(re.findall(r'(?<![:\w-])columns="?(\d+)"?', tag))
            grid_minimums |= _literal(tag, "min")
            grid_flags |= {
                flag
                for flag in documented["grid.flags"]
                if re.search(rf"(?<![\w-]){re.escape(flag)}(?![\w-])", tag)
            }

    assert set(documented["button.variant"]) <= button_variants
    assert (
        set(documented["button.size"]) | set(documented["button.size.experimental"])
        <= button_sizes
    )
    assert set(documented["pill.variant"]) <= pill_variants
    assert set(documented["grid.min"]) <= grid_minimums
    assert set(documented["grid.flags"]) <= grid_flags
    assert set(documented["grid.columns"]) - grid_columns == set(
        audit["grid.columns.no-caller"]
    )


def test_design_kit_keeps_the_experimental_sizes_in_its_loops() -> None:
    documented = _documented()
    showcase = SHOWCASE.read_text(encoding="utf-8")
    expected = set(documented["button.size"]) | set(
        documented["button.size.experimental"]
    )

    assert expected <= _loop_sizes(showcase)
    assert showcase.count('{% for group_size in ["xs", "sm", "md", "lg", "xl"] %}') == 2


def test_reserved_shape_keeps_its_callers_and_remains_unstyled() -> None:
    documented = _documented()
    shapes = set(documented["button.shape.reserved-noop"])

    passed = {
        shape
        for path, source in _templates().items()
        if path != SHOWCASE
        for tag in _button_tags(source)
        for shape in _literal(tag, "shape")
    }
    assert "square" in passed
    for name in (
        "layout/Topbar.jinja",
        "common/MenuTrigger.jinja",
        "common/IconButton.jinja",
    ):
        assert 'shape="square"' in (COMPONENTS / name).read_text(encoding="utf-8"), name
    assert "btn-{{ shape }}" in (COMPONENTS / "common" / "ButtonGroup.jinja").read_text(
        encoding="utf-8"
    )
    assert 'shape="square"' in SHOWCASE.read_text(encoding="utf-8")
    assert 'shape="round"' in BUTTON_JINJA.read_text(encoding="utf-8").splitlines()[0]

    all_component_classes = set().union(
        *(_classes(stylesheet) for stylesheet in COMPONENTS.rglob("*.css"))
    )
    assert not {f"btn-{shape}" for shape in shapes} & all_component_classes


def test_pill_design_kit_only_variants_keep_their_specimens() -> None:
    documented = set(_documented()["pill.variant"])
    showcase_only = set(_audit()["pill.design-kit-only"])
    showcase = SHOWCASE.read_text(encoding="utf-8")

    assert showcase_only <= documented
    for variant in showcase_only:
        assert f'variant="{variant}"' in showcase
        for path, source in _templates().items():
            if path != SHOWCASE:
                assert variant not in _pill_variants(source), path


def test_audited_tokens_match_the_tree() -> None:
    audit = _audit()
    main_css = MAIN_CSS.read_text(encoding="utf-8")
    frontend = "\n".join(
        path.read_text(encoding="utf-8")
        for path in COMPONENTS.parent.rglob("*")
        if path.is_file() and path.suffix in {".css", ".jinja", ".js", ".mjs", ".py"}
    )

    for token in audit["token.removed"]:
        assert token not in main_css, token
        assert token not in frontend, token
    for token in audit["token.retained"]:
        assert token in main_css, token


def test_unsupported_values_are_rejected_at_render() -> None:
    """T19 enforces the documented vocabulary; nothing renders unstyled.

    The T18 record proved these values were undeclared and had no rule. Since
    T19 they fail at render with a diagnostic naming the component, argument and
    value, so a caller cannot ship a class nobody styles.
    """
    documented = _documented()

    for name, props, argument, value in (
        ("common.Button", {"variant": "ghost"}, "variant", "ghost"),
        ("common.Button", {"size": "xxl"}, "size", "xxl"),
        ("common.Pill", {"variant": "ghost"}, "variant", "ghost"),
        ("common.Grid", {"columns": 4}, "columns", "4"),
        ("common.Grid", {"gap": 7}, "gap", "7"),
        ("common.Grid", {"min": "huge"}, "min", "huge"),
    ):
        with pytest.raises(ComponentOptionError) as error:
            _render(name, **props)
        message = str(error.value)
        assert name in message and argument in message and value in message, message

    assert "4" not in documented["grid.columns"]
    assert "7" not in documented["grid.gap"]
    assert "huge" not in documented["grid.min"]
