"""Component tests for the standalone auth surface.

The login page is the product's cover and colophon: it renders through
``layout.BlankPage`` (no rail, topbar or palette), and its form must submit
with and without JavaScript. Focus after the htmx replacement lands on the
error summary, which ``Login.js`` owns.
"""

import pytest

pytestmark = pytest.mark.frontend


def test_the_page_carries_no_shell_controls(component):
    page = component.mount("pages.login.Login")

    assert page.locator(".login-cover").count() == 1
    assert page.locator(".login-panel").count() == 1
    assert page.locator("#rail").count() == 0
    assert page.locator(".topbar").count() == 0
    assert page.locator("#drawer-toggle").count() == 0
    assert page.locator("#user-menu-trigger").count() == 0
    assert page.locator("#palette").count() == 0


def test_the_form_submits_without_javascript(component):
    page = component.mount("pages.login.Login")

    form = page.locator("form.login-form").first
    assert form.get_attribute("method") == "post"
    assert form.get_attribute("action") == "/auth/login-form"
    assert form.get_attribute("hx-ext") == "ignore:json-enc"
    assert form.locator('button[type="submit"]').count() == 1
    assert form.locator('#email[autocomplete="email"]').count() == 1
    assert form.locator('#password[autocomplete="current-password"]').count() == 1


def test_the_register_variant_points_at_the_register_form(component):
    page = component.mount("pages.login.Login", props={"mode": "register"})

    form = page.locator("form.login-form").first
    assert form.get_attribute("action") == "/auth/register-form"
    assert form.locator("#name").count() == 1
    assert form.locator('#password[autocomplete="new-password"]').count() == 1


def test_the_error_summary_takes_focus_after_a_swap(component):
    page = component.mount(
        "pages.login.Login", props={"error": "Email o password non validi"}
    )

    assert page.locator("[data-login-error]").count() == 1
    component.emit_htmx_after_swap()

    assert page.evaluate(
        "() => document.activeElement === document.querySelector('[data-login-error]')"
    )


def test_the_google_button_only_renders_when_enabled(component):
    without = component.mount("pages.login.Login")
    assert without.locator("text=Continua con Google").count() == 0

    with_google = component.mount("pages.login.Login", props={"google_enabled": True})
    assert with_google.locator("text=Continua con Google").count() == 1
