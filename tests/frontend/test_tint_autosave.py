"""The tint picker's autosave integration (REQ-0008/T02).

One registered field: the picker's radios write the hidden input that the
autosave controller owns, so a choice is previewed immediately, sent as the
canonical ``p1``–``p12`` value, and repainted when a value is applied (a
restored draft) — never as twelve competing fields.
"""

import pytest

pytestmark = pytest.mark.frontend

AUTOSAVE = "/api/worlds/w/sessions/1"

TINTS = [
    {"value": "p1", "label": "Vermiglio"},
    {"value": "p5", "label": "Bosco"},
    {"value": "p8", "label": "Cobalto"},
]


def _mount(component, **route):
    component.route_json("PATCH", AUTOSAVE, **route)
    page = component.mount(
        "editorial.Metadata",
        props={
            "fields": [
                {
                    "name": "real_date",
                    "label": "Data reale",
                    "kind": "date",
                    "value": "2026-10-06",
                },
                {
                    "name": "tint",
                    "label": "Colore",
                    "kind": "tint",
                    "value": "p5",
                    "options": TINTS,
                },
            ],
            "base": "/worlds/w/sessions/1",
            "version": "1",
            "can_manage": True,
        },
    )
    page.add_script_tag(url="/static/js/editor.js")
    page.wait_for_selector("[data-tint-picker]")
    return page


def _state(page) -> dict:
    return page.evaluate(
        """() => {
            const root = document.querySelector('[data-tint-picker]');
            const hidden = root.querySelector('[data-tint-value]');
            return {
                value: hidden.value,
                name: root.querySelector('[data-tint-name]').textContent.trim(),
                fields: document.querySelectorAll('[data-metadata-field]').length,
                checked: root.querySelector('input:checked')?.value,
            };
        }"""
    )


def test_choosing_a_tint_sends_the_canonical_value(component):
    page = _mount(component, body={"version": 2})

    page.click("#tint-picker-trigger")
    page.wait_for_selector("#tint-picker-panel:popover-open")
    page.click("#tint-picker-panel input[value='p8']")
    page.wait_for_timeout(1200)

    state = _state(page)
    assert state["value"] == "p8"
    assert state["name"] == "Cobalto"
    # One field per metadata control, not one per radio.
    assert state["fields"] == 2
    assert any(method == "PATCH" for method, _ in component.requests())


def test_the_preview_is_immediate_and_the_save_keeps_the_body(component):
    page = _mount(component, body={"version": 2}, delay_ms=600)

    page.click("#tint-picker-trigger")
    page.wait_for_selector("#tint-picker-panel:popover-open")
    page.click("#tint-picker-panel input[value='p1']")

    # The local preview is immediate; persistence follows on the wire.
    assert _state(page)["value"] == "p1"
    page.wait_for_timeout(1200)
    assert _state(page)["name"] == "Vermiglio"


def test_a_conflict_keeps_the_local_choice(component):
    component.allow_console_errors("409 (Conflict)")
    page = _mount(component, status=409, body={})

    page.click("#tint-picker-trigger")
    page.wait_for_selector("#tint-picker-panel:popover-open")
    page.click("#tint-picker-panel input[value='p8']")
    page.wait_for_selector(".autosave-recovery", timeout=5000)

    state = _state(page)
    assert state["value"] == "p8"
    assert state["name"] == "Cobalto"


def test_an_applied_value_repaints_the_picker(component):
    page = _mount(component, body={"version": 2})

    page.evaluate(
        """() => {
            const hidden = document.querySelector('[data-tint-value]');
            hidden.value = 'p1';
            hidden.dispatchEvent(new Event('change', { bubbles: true }));
        }"""
    )

    state = _state(page)
    assert state["checked"] == "p1"
    assert state["name"] == "Vermiglio"
