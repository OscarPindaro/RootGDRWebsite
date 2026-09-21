"""Asset delivery: a full page and an htmx fragment both style Button and Field.

``{#css #}`` is what makes a component's asset reachable from a render that
never goes through ``layout.BlankPage`` — an htmx fragment. These tests assert
computed styles and parsed stylesheets rather than the presence of a ``<link>``:
a link that 404s, or one whose rules lose the cascade, passes a presence check.
"""

import pytest

pytestmark = pytest.mark.frontend

BUTTON = ".btn"
FIELD = ".field"


def _token(page, name: str) -> str:
    return page.evaluate(
        "name => getComputedStyle(document.documentElement)"
        ".getPropertyValue(name).trim()",
        name,
    )


def _assert_button_is_styled(page) -> None:
    """Button.css gives the button its height, its atlas radius and its centring.

    A user-agent button has no height, no radius, and ``normal`` alignment, so
    these three fail together when the stylesheet never arrives.
    """
    button = page.locator(BUTTON).first

    assert button.evaluate("el => getComputedStyle(el).height") == _token(
        page, "--button-height-md"
    )
    assert button.evaluate("el => getComputedStyle(el).borderRadius") == _token(
        page, "--radius"
    )
    assert button.evaluate("el => getComputedStyle(el).alignItems") == "center"


def _assert_field_is_styled(page) -> None:
    """Field.css stacks label, input and supporting text in a column."""
    field = page.locator(FIELD).first

    assert field.evaluate("el => getComputedStyle(el).display") == "flex"
    assert field.evaluate("el => getComputedStyle(el).flexDirection") == "column"
    assert page.locator(".field-label").first.evaluate(
        "el => getComputedStyle(el).fontWeight"
    ) == _token(page, "--weight-medium")


def test_a_full_page_styles_button_and_field(component):
    page = component.mount("pages.login.Login")

    _assert_button_is_styled(page)
    _assert_field_is_styled(page)


def test_a_fragment_styles_button_and_field(component):
    page = component.mount("pages.admin.InviteDialog", props={"roles": []})

    _assert_button_is_styled(page)
    _assert_field_is_styled(page)


def test_every_stylesheet_the_fragment_needs_was_fetched_and_parsed(component):
    """The fragment's own sheet and its children's arrive, not just the page's."""
    page = component.mount("pages.admin.InviteDialog", props={"roles": []})

    sheets = page.evaluate(
        """() => [...document.styleSheets].map(sheet => ({
            href: sheet.href || '',
            rules: (() => { try { return sheet.cssRules.length } catch { return -1 } })(),
        }))"""
    )
    rules_by_href = {sheet["href"]: sheet["rules"] for sheet in sheets}

    for asset in (
        "common/Button.css",
        "common/Field.css",
        "pages/admin/InviteDialog.css",
    ):
        href = next((url for url in rules_by_href if url.endswith(asset)), None)
        assert href is not None, f"{asset} was never loaded: {sorted(rules_by_href)}"
        assert rules_by_href[href] > 0, f"{asset} loaded but parsed to no rules"
