"""The session picker inside the metadata panel (REQ-0010/T03).

The checkboxes are the control; the hidden multiple select is the one field the
autosave registers. The filter hides what does not match and is not selected, so
a chosen session never disappears, and an applied value repaints the boxes.
"""

import pytest

from backend.navigation import MetadataField, Option

pytestmark = pytest.mark.frontend

AUTOSAVE = "/api/worlds/w/stories/1"

OPTIONS = [
    {"value": "s1", "label": "Primavera, 3° anno · Il risveglio"},
    {"value": "s2", "label": "Autunno, 3° anno · L'inverno dei corvi"},
    {"value": "s3", "label": "Inverno, 4° anno · La marcia delle ombre"},
    {"value": "s4", "label": "Data da definire · Nuova sessione"},
]


def _mount(component, **route):
    component.route_json("PATCH", AUTOSAVE, **route)
    page = component.mount(
        "editorial.Metadata",
        props={
            "fields": [
                MetadataField(
                    name="session_ids",
                    label="Sessioni",
                    kind="sessions",
                    values=["s1", "s2"],
                    options=[Option(**option) for option in OPTIONS],
                )
            ],
            "base": "/worlds/w/stories/1",
            "version": "1",
            "can_manage": True,
        },
    )
    page.add_script_tag(url="/static/js/editor.js")
    page.wait_for_selector("[data-session-picker]")
    return page


def _field(page) -> dict:
    return page.evaluate(
        """() => {
            const value = document.querySelector('[data-session-value]');
            return {
                name: value.name,
                multiple: value.multiple,
                fields: document.querySelectorAll('[data-metadata-field]').length,
                selected: [...value.options].filter((o) => o.selected).map((o) => o.value),
                checked: [...document.querySelectorAll('[data-session-choice]')]
                    .filter((box) => box.checked).map((box) => box.value),
            };
        }"""
    )


def test_one_registered_field_holds_the_selection(component):
    page = _mount(component, body={"version": 2})

    field = _field(page)
    assert field["name"] == "session_ids"
    assert field["multiple"] is True
    assert field["fields"] == 1
    assert field["selected"] == ["s1", "s2"]
    assert field["checked"] == ["s1", "s2"]


def test_checking_a_session_sends_the_ids(component):
    page = _mount(component, body={"version": 2})

    page.click("[data-session-choice][value='s3']")
    page.wait_for_timeout(1200)

    field = _field(page)
    assert field["selected"] == ["s1", "s2", "s3"]
    assert any(method == "PATCH" for method, _ in component.requests())


def test_the_filter_keeps_selected_sessions_visible(component):
    page = _mount(component)

    page.fill("[data-session-filter]", "inverno")
    state = page.evaluate(
        """() => [...document.querySelectorAll('[data-session-option]')]
            .map((el) => ({hidden: el.hidden, checked: el.querySelector('input').checked}))"""
    )
    # The matching one is visible; the other selected ones stay; the rest hides.
    assert state[2] == {"hidden": False, "checked": False}
    assert state[0] == {"hidden": False, "checked": True}
    assert state[1] == {"hidden": False, "checked": True}
    assert state[3]["hidden"] is True

    # A filter that matches nothing still shows the chosen sessions and hides
    # the "nothing matches" note, because the list is not empty.
    page.fill("[data-session-filter]", "inesistente")
    kept = page.evaluate(
        """() => ({
            visible: [...document.querySelectorAll('[data-session-option]')]
                .filter((el) => !el.hidden).length,
            message: !document.querySelector('[data-session-empty]').hidden,
        })"""
    )
    assert kept == {"visible": 2, "message": False}


def test_a_filter_that_matches_nothing_says_so(component):
    page = _mount(component)
    page.evaluate(
        """() => {
            document.querySelectorAll('[data-session-choice]').forEach((box) => {
                box.checked = false;
            });
            document.querySelector('[data-session-filter]').value = 'inesistente';
            document.querySelector('[data-session-filter]')
                .dispatchEvent(new Event('input', { bubbles: true }));
        }"""
    )

    state = page.evaluate(
        """() => ({
            visible: [...document.querySelectorAll('[data-session-option]')]
                .filter((el) => !el.hidden).length,
            message: !document.querySelector('[data-session-empty]').hidden,
        })"""
    )
    assert state == {"visible": 0, "message": True}


def test_an_applied_value_repaints_the_boxes(component):
    page = _mount(component, body={"version": 2})

    page.evaluate(
        """() => {
            const value = document.querySelector('[data-session-value]');
            [...value.options].forEach((option) => {
                option.selected = option.value === 's3';
            });
            value.dispatchEvent(new Event('change', { bubbles: true }));
        }"""
    )

    field = _field(page)
    assert field["checked"] == ["s3"]
