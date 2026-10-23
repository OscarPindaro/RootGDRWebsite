"""Render-time enforcement of the shared component vocabulary.

REQ-0019/T19. The accepted finite choices are recorded in
``docs/features-implemented/component-vocabulary.md``; these tests pin that
every recorded value still renders, that an undeclared one fails with a
diagnostic naming the component, argument and value, and that native HTML
attributes keep passing through untouched.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from backend.jinja import ComponentOptionError, get_catalog

COMPONENTS = Path(__file__).parents[3] / "src" / "frontend" / "components"
MANUAL = (
    Path(__file__).parents[3]
    / "docs"
    / "features-implemented"
    / "component-vocabulary.md"
)


def _documented() -> dict[str, list[str]]:
    text = MANUAL.read_text(encoding="utf-8")
    block = text.split("<!-- component-vocabulary:start -->", 1)[1].split(
        "<!-- component-vocabulary:end -->", 1
    )[0]
    return {
        match.group(1): match.group(2).split()
        for line in block.splitlines()
        if (match := re.match(r"^([a-z.-]+):\s*(.+?)\s*$", line))
    }


def _render(name: str, **props: object) -> str:
    return str(
        get_catalog(str(COMPONENTS), app_name="Root GDR").render(
            name, _content="x", **props
        )
    )


def test_every_documented_button_variant_renders() -> None:
    for variant in _documented()["button.variant"]:
        assert f"btn-{variant}" in _render("common.Button", variant=variant)


def test_every_documented_button_size_renders() -> None:
    documented = _documented()
    for size in documented["button.size"] + documented["button.size.experimental"]:
        assert f"btn-{size}" in _render("common.Button", size=size)


def test_the_reserved_shape_argument_stays_accepted() -> None:
    for shape in _documented()["button.shape.reserved-noop"]:
        assert f"btn-{shape}" in _render("common.Button", shape=shape)


def test_every_documented_pill_variant_renders() -> None:
    for variant in _documented()["pill.variant"]:
        assert f'class="pill pill-{variant}"' in _render("common.Pill", variant=variant)


def test_every_documented_grid_choice_renders() -> None:
    documented = _documented()
    for columns in documented["grid.columns"]:
        assert f"grid-columns-{columns}" in _render("common.Grid", columns=columns)
    for gap in documented["grid.gap"]:
        assert f"--grid-gap: var(--sp-{gap});" in _render("common.Grid", gap=gap)
    for minimum in documented["grid.min"]:
        assert f"--grid-min: var(--grid-min-{minimum});" in _render(
            "common.Grid", min=minimum
        )


@pytest.mark.parametrize(
    ("name", "props", "component", "argument", "value"),
    [
        ("common.Button", {"variant": "ghost"}, "common.Button", "variant", "ghost"),
        ("common.Button", {"size": "huge"}, "common.Button", "size", "huge"),
        ("common.Pill", {"variant": "ghost"}, "common.Pill", "variant", "ghost"),
        ("common.Grid", {"columns": 4}, "common.Grid", "columns", "4"),
        ("common.Grid", {"gap": 7}, "common.Grid", "gap", "7"),
        ("common.Grid", {"min": "huge"}, "common.Grid", "min", "huge"),
    ],
)
def test_an_undeclared_value_is_rejected(
    name: str, props: dict, component: str, argument: str, value: str
) -> None:
    with pytest.raises(ComponentOptionError) as error:
        _render(name, **props)

    message = str(error.value)
    assert message.startswith(component)
    assert f"argument '{argument}'" in message
    assert f"'{value}'" in message
    assert "expected one of:" in message


def test_a_computed_value_is_checked_when_the_component_renders() -> None:
    """``ConfirmDialog`` passes ``:variant="confirm_variant"`` to Button."""
    assert "btn-danger" in _render(
        "common.ConfirmDialog", message="x", confirm_variant="danger"
    )
    with pytest.raises(
        ComponentOptionError,
        match=r"common\.Button: argument 'variant' does not accept 'ghost'",
    ):
        _render("common.ConfirmDialog", message="x", confirm_variant="ghost")


def test_native_attributes_and_classes_pass_through() -> None:
    html = _render(
        "common.Button",
        variant="secondary",
        **{"class": "extra", "data-testid": "save", "aria-describedby": "hint"},
    )

    assert 'data-testid="save"' in html
    assert 'aria-describedby="hint"' in html
    assert 'class="extra btn btn-secondary btn-md btn-round"' in html


def test_grid_keeps_optional_columns_and_minimum_unset() -> None:
    html = _render("common.Grid")

    assert "grid-columns-" not in html
    assert "grid-auto" not in html
    assert "--grid-min" not in html
