"""Focused rendering tests for expressive buttons and button groups."""

from pathlib import Path

from backend.jinja import get_catalog
from backend.navigation import ButtonGroupOption

COMPONENTS = Path(__file__).parents[3] / "src" / "frontend" / "components"


def _catalog():
    return get_catalog(str(COMPONENTS), app_name="Root GDR")


def test_button_supports_sizes_shapes_icons_and_toggle_state() -> None:
    html = str(
        _catalog().render(
            "common.Button",
            variant="secondary",
            size="xl",
            shape="square",
            icon="star",
            selected=True,
            content="Preferito",
        )
    )

    assert (
        'class="btn btn-secondary btn-xl btn-square btn-mixed btn-toggle btn-selected"'
        in html
    )
    assert 'aria-pressed="true"' in html
    assert 'data-lucide="star"' in html
    assert "Preferito" in html


def test_single_selection_group_uses_real_required_radio_inputs() -> None:
    html = str(
        _catalog().render(
            "common.ButtonGroup",
            label="Vista",
            name="view",
            selection="single",
            required=True,
            variant="connected",
            size="sm",
            options=[
                ButtonGroupOption(value="list", label="Elenco", icon="list"),
                ButtonGroupOption(value="grid", label="Griglia", disabled=True),
            ],
            value="list",
        )
    )

    assert "button-group-connected button-group-sm" in html
    assert html.count('type="radio"') == 2
    assert 'value="list" aria-label="Elenco" checked required' in html
    assert 'value="grid" aria-label="Griglia" required disabled' in html
    assert "<legend" in html and "Vista" in html


def test_multi_selection_group_uses_checked_checkbox_inputs() -> None:
    html = str(
        _catalog().render(
            "common.ButtonGroup",
            label="Filtri",
            name="filters",
            selection="multi",
            options=[
                ButtonGroupOption(value="people", label="Personaggi"),
                ButtonGroupOption(value="places", label="Luoghi"),
            ],
            values=["people"],
        )
    )

    assert html.count('type="checkbox"') == 2
    assert 'value="people" aria-label="Personaggi" checked' in html
    assert 'value="places" aria-label="Luoghi" checked' not in html


def test_action_group_keeps_slotted_buttons() -> None:
    html = str(
        _catalog().render(
            "common.ButtonGroup",
            label="Azioni",
            variant="standard",
            content='<button class="btn">Uno</button><button class="btn">Due</button>',
        )
    )

    assert 'role="group" aria-label="Azioni"' in html
    assert html.count("<button") == 2
