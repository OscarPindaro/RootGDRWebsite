"""Component tests for the account Settings page (F18).

Settings used to be a bare form: one control and a hint. It is now a real
settings page — a group with a heading and a labelled preference row that
explains itself — and the control still saves on change, with no save button.
The polite feedback region belongs to the page, not to the control.
"""

from types import SimpleNamespace

import pytest

from backend.navigation import ButtonGroupOption

pytestmark = pytest.mark.frontend


def _user(symbol_style: str = "icons") -> SimpleNamespace:
    return SimpleNamespace(
        name="Ada",
        email="ada@example.com",
        role="member",
        avatar_url=None,
        symbol_style=symbol_style,
    )


def _options() -> list[ButtonGroupOption]:
    return [
        ButtonGroupOption(value="icons", label="Icone"),
        ButtonGroupOption(value="shapes", label="Forme"),
    ]


def _settings(component, symbol_style: str = "icons"):
    return component.mount(
        "pages.settings.Settings",
        props={
            "current_user": _user(symbol_style),
            "symbol_style_options": _options(),
        },
    )


def test_the_page_groups_the_preference_under_a_heading(component):
    page = _settings(component)

    assert page.locator(".section__head h2").inner_text().strip() == "Aspetto"
    assert page.locator(".settings-row__title").inner_text().strip() == "Simboli"
    description = page.locator(".settings-row__description").inner_text()
    assert "Icone" in description and "Forme" in description


def test_the_control_posts_on_change_to_the_page_status(component):
    page = _settings(component)

    form = page.locator("form.settings-form")
    assert form.get_attribute("hx-post") == "/settings"
    assert form.get_attribute("hx-trigger") == "change"
    assert form.get_attribute("hx-target") == "#settings-status"
    assert form.get_attribute("hx-ext") == "ignore:json-enc"
    # A no-JavaScript fallback still submits the form natively.
    assert form.get_attribute("method") == "post"
    assert form.get_attribute("action") == "/settings"

    radios = page.locator('input[name="symbol_style"]')
    assert radios.count() == 2
    assert page.locator('input[name="symbol_style"]:checked').count() == 1


def test_there_is_no_visible_save_control(component):
    """The change is the save; the only submit lives inside <noscript>."""
    page = _settings(component)

    assert page.locator('.settings-form button[type="submit"]').count() == 0
    assert "<noscript>" in page.content()


def test_the_status_region_is_polite_and_scoped_to_the_form(component):
    page = _settings(component)

    status = page.locator("#settings-status")
    assert status.get_attribute("aria-live") == "polite"
    assert status.get_attribute("aria-atomic") == "true"
    assert status.inner_text().strip() == ""
    assert status.evaluate("el => Boolean(el.closest('form.settings-form'))")


def test_the_status_fragment_is_not_assertive_and_echoes_the_style(component):
    page = component.mount(
        "pages.settings.SettingsStatus", props={"symbol_style": "shapes"}
    )

    assert page.locator("[data-symbol-style='shapes']").count() == 1
    assert page.locator('[role="alert"]').count() == 0
    assert "Preferenza salvata." in page.content()


def test_the_page_declares_the_status_fragment_assets(component):
    """The success message arrives through htmx; Alert.css must be on the host."""
    page = _settings(component)

    hrefs = page.evaluate(
        "() => [...document.styleSheets].map(sheet => sheet.href || '')"
    )
    assert any(url.endswith("common/Alert.css") for url in hrefs)
