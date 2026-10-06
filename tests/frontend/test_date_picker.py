"""The hybrid date picker (REQ-0007/T02).

The native input stays canonical: typed entry works, an invalid entry leaves it
empty, and the desktop calendar only writes a real date. Dates are local
calendar dates, so a leap day and a month or year boundary behave as written;
a phone keeps the platform picker and the atlas grid is not offered.
"""

import pytest

pytestmark = pytest.mark.frontend

AUTOSAVE = "/api/worlds/w/sessions/1"


def _mount(component, value="2026-10-06", **route):
    component.route_json("PATCH", AUTOSAVE, **route)
    page = component.mount(
        "common.DatePicker",
        props={
            "name": "real_date",
            "value": value,
            "label": "Data reale",
            "id": "date",
        },
    )
    page.add_script_tag(url="/static/components/common/DatePicker.js")
    page.wait_for_selector("[data-date-picker]")
    return page


def _state(page) -> dict:
    return page.evaluate(
        """() => {
            const root = document.querySelector('[data-date-picker]');
            return {
                value: root.querySelector('[data-date-input]').value,
                month: root.querySelector('[data-date-month]').textContent,
                open: root.querySelector('.date-picker__panel').matches(':popover-open'),
                selected: root.querySelector('.date-picker__day[aria-selected="true"]')?.dataset.date,
            };
        }"""
    )


def test_the_trigger_opens_the_month_of_the_value(component):
    page = _mount(component)

    page.click("[data-date-open]")
    page.wait_for_selector(".date-picker__panel:popover-open")

    state = _state(page)
    assert state["month"] == "ottobre 2026"
    assert state["selected"] == "2026-10-06"


def test_picking_a_day_writes_the_canonical_value_and_closes(component):
    page = _mount(component)

    page.click("[data-date-open]")
    page.wait_for_selector(".date-picker__panel:popover-open")
    page.click('[data-date="2026-10-21"]')

    page.wait_for_function(
        "() => !document.querySelector('.date-picker__panel').matches(':popover-open')"
    )
    assert _state(page)["value"] == "2026-10-21"


def test_today_and_clear_actions(component):
    page = _mount(component)

    page.click("[data-date-open]")
    page.wait_for_selector(".date-picker__panel:popover-open")
    page.click("[data-date-today]")
    today = page.evaluate(
        "() => { const d = new Date(); const p = (n) => String(n).padStart(2, '0'); return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())}`; }"
    )
    assert _state(page)["value"] == today

    page.click("[data-date-open]")
    page.wait_for_selector(".date-picker__panel:popover-open")
    page.click("[data-date-clear]")
    # The nullable contract: clearing leaves the field empty.
    assert _state(page)["value"] == ""


def test_a_leap_day_exists_and_the_year_rolls_over(component):
    page = _mount(component, value="2028-02-29")

    page.click("[data-date-open]")
    page.wait_for_selector(".date-picker__panel:popover-open")
    assert _state(page)["month"] == "febbraio 2028"
    assert page.locator('[data-date="2028-02-29"]').count() == 1

    page.click("[data-date-next]")
    assert _state(page)["month"] == "marzo 2028"

    for _ in range(10):
        page.click("[data-date-next]")
    assert _state(page)["month"] == "gennaio 2029"

    page.click("[data-date-prev]")
    assert _state(page)["month"] == "dicembre 2028"


def test_the_keyboard_walks_the_grid(component):
    page = _mount(component)

    page.click("[data-date-open]")
    page.wait_for_selector(".date-picker__panel:popover-open")
    focused = lambda: page.evaluate("() => document.activeElement?.dataset?.date")

    page.keyboard.press("ArrowRight")
    assert focused() == "2026-10-07"
    page.keyboard.press("ArrowDown")
    assert focused() == "2026-10-14"
    page.keyboard.press("Home")
    assert focused() == "2026-10-12"
    page.keyboard.press("End")
    assert focused() == "2026-10-18"
    page.keyboard.press("PageDown")
    assert _state(page)["month"] == "novembre 2026"
    page.keyboard.press("PageUp")
    assert _state(page)["month"] == "ottobre 2026"

    page.keyboard.press("Enter")
    assert _state(page)["value"] == "2026-10-18"
    assert _state(page)["open"] is False


def test_escape_closes_and_returns_focus(component):
    page = _mount(component)

    page.click("[data-date-open]")
    page.wait_for_selector(".date-picker__panel:popover-open")
    page.keyboard.press("Escape")
    page.wait_for_function(
        "() => !document.querySelector('.date-picker__panel').matches(':popover-open')"
    )
    assert page.evaluate(
        "() => document.activeElement.closest('[data-date-picker]') !== null"
    )


def test_an_invalid_typed_date_leaves_the_field_empty(component):
    page = _mount(component)

    # Even forced through the DOM, the native input refuses an impossible date
    # (Playwright will not even type one), so nothing wrong can be stored.
    page.evaluate(
        """() => {
            document.querySelector('[data-date-input]').value = '2026-02-30';
        }"""
    )

    assert _state(page)["value"] == ""


def test_a_phone_keeps_the_native_input(component):
    page = _mount(component)
    page.set_viewport_size({"width": 390, "height": 844})

    assert page.locator("[data-date-open]").is_hidden()
    assert page.locator("[data-date-input]").is_visible()
