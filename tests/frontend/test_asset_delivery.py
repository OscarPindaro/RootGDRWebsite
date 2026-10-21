"""Asset delivery: what an isolated mount proves and what only a host can.

``{#css #}`` is what makes a component's asset reachable from a render that
never goes through ``layout.BlankPage`` — an htmx fragment. An isolated mount is
wrapped in a shell that writes every asset the fragment collected, so it proves
the declarations and nothing about the page that receives the fragment. The host
tests below load the admin page as the backend returns it, then swap the
fragment markup the backend returns, so the assets in play are the ones the host
itself emits. Computed styles and parsed stylesheets are asserted throughout: a
link that 404s, or one whose rules lose the cascade, passes a presence check.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.jinja import get_catalog

pytestmark = pytest.mark.frontend

COMPONENTS = Path(__file__).parents[2] / "src" / "frontend" / "components"
BUTTON = ".btn"
FIELD = ".field"
DIALOG = "dialog[data-dialog]"
INVITE_ASSETS = (
    "common/Alert.css",
    "common/Button.css",
    "common/Dialog.css",
    "common/Field.css",
    "common/Tooltip.css",
    "pages/admin/InviteDialog.css",
)
ROLES = [
    {"value": "member", "label": "Member"},
    {"value": "admin", "label": "Admin"},
]


def _render(component: str, **props) -> str:
    catalog = get_catalog(str(COMPONENTS), env="dev", app_name="harness-frontend")
    return str(catalog.render(component, **props))


def _invite_fragment() -> str:
    return _render("pages.admin.InviteDialog", roles=ROLES)


def _admin_props() -> dict:
    return {
        "users": [],
        "invitations": [],
        "current_user": SimpleNamespace(
            name="Ada",
            email="ada@example.com",
            role="admin",
            avatar_url=None,
            symbol_style="icons",
        ),
    }


def _admin_host() -> str:
    return _render("pages.admin.AdminDashboard", **_admin_props())


def _open_raw_admin_host(component):
    """Load the page document the backend returns, not the component shell.

    ``component.mount`` supplies the ephemeral server and a fresh context. The
    shell document is then replaced by navigating to the host render, so only
    the stylesheets and scripts the host emits can style or initialize the
    fragment that arrives later.
    """
    page = component.mount("pages.admin.AdminDashboard", props=_admin_props())
    raw = f"{page.url.rstrip('/')}/admin/users"
    page.route(
        raw,
        lambda route: route.fulfill(
            status=200, content_type="text/html", body=_admin_host()
        ),
    )
    page.goto(raw, wait_until="load")
    page.wait_for_function("() => Boolean(window.rootGdrDialog)")
    return page


def _swap_invite_fragment(page, fragment: str) -> None:
    """Perform the innerHTML swap htmx performs into ``#invite-dialog``."""
    page.evaluate(
        """html => {
            const host = document.getElementById('invite-dialog');
            host.innerHTML = html;
            host.dispatchEvent(new CustomEvent('htmx:afterSwap', {
                bubbles: true, detail: {elt: host},
            }));
        }""",
        fragment,
    )


def _token(page, name: str) -> str:
    return page.evaluate(
        "name => getComputedStyle(document.documentElement)"
        ".getPropertyValue(name).trim()",
        name,
    )


def _parsed_sheets(page) -> dict[str, int]:
    sheets = page.evaluate(
        """() => [...document.styleSheets].map(sheet => ({
            href: sheet.href || '',
            rules: (() => { try { return sheet.cssRules.length } catch { return -1 } })(),
        }))"""
    )
    return {sheet["href"]: sheet["rules"] for sheet in sheets}


def _assert_sheets_parsed(page, assets) -> None:
    rules_by_href = _parsed_sheets(page)

    for asset in assets:
        href = next((url for url in rules_by_href if url.endswith(asset)), None)
        assert href is not None, f"{asset} was never loaded: {sorted(rules_by_href)}"
        assert rules_by_href[href] > 0, f"{asset} loaded but parsed to no rules"


def _assert_button_is_styled(page, root: str = "body") -> None:
    """Button.css gives the button its height, its atlas radius and its centring.

    A user-agent button has no height, no radius, and ``normal`` alignment, so
    these three fail together when the stylesheet never arrives.
    """
    button = page.locator(f"{root} {BUTTON}").first

    assert button.evaluate("el => getComputedStyle(el).height") == _token(
        page, "--button-height-md"
    )
    assert button.evaluate("el => getComputedStyle(el).borderRadius") == _token(
        page, "--radius"
    )
    assert button.evaluate("el => getComputedStyle(el).alignItems") == "center"


def _assert_field_is_styled(page, root: str = "body") -> None:
    """Field.css stacks label, input and supporting text in a column.

    The label is the floating M3 label (``.field__label``), so the assertion
    pins the anatomy's own class rather than the legacy ``.field-label``.
    """
    field = page.locator(f"{root} {FIELD}").first

    assert field.evaluate("el => getComputedStyle(el).display") == "flex"
    assert field.evaluate("el => getComputedStyle(el).flexDirection") == "column"
    assert page.locator(f"{root} .field__label").first.evaluate(
        "el => getComputedStyle(el).fontWeight"
    ) == _token(page, "--weight-medium")


def _assert_dialog_is_styled(page, root: str = "body") -> None:
    """Dialog.css owns the surface and the form stacks its controls."""
    dialog = page.locator(f"{root} {DIALOG}").first

    assert dialog.evaluate("el => getComputedStyle(el).borderRadius") == _token(
        page, "--radius-lg"
    )
    assert dialog.evaluate("el => getComputedStyle(el).padding") == "0px"
    assert (
        page.locator(f"{root} .dialog-container").first.evaluate(
            "el => getComputedStyle(el).flexDirection"
        )
        == "column"
    )
    assert (
        page.locator(f"{root} .invite-form").first.evaluate(
            "el => getComputedStyle(el).flexDirection"
        )
        == "column"
    )


def test_a_full_page_styles_button_and_field(component):
    page = component.mount("pages.login.Login")

    _assert_button_is_styled(page)
    _assert_field_is_styled(page)


def test_an_isolated_fragment_mount_styles_button_and_field(component):
    page = component.mount("pages.admin.InviteDialog", props={"roles": ROLES})

    _assert_button_is_styled(page)
    _assert_field_is_styled(page)
    _assert_dialog_is_styled(page)


def test_every_stylesheet_the_isolated_mount_needs_was_fetched_and_parsed(component):
    """The fragment's own sheet and its children's arrive, not just the page's."""
    page = component.mount("pages.admin.InviteDialog", props={"roles": ROLES})

    _assert_sheets_parsed(page, INVITE_ASSETS)


def test_the_fragment_markup_carries_no_assets_of_its_own():
    """The backend response is markup; only a host page can supply the assets."""
    fragment = _invite_fragment()

    assert "<link" not in fragment
    assert "<script" not in fragment
    assert "<dialog" in fragment
    assert "Invita utente" in fragment


def test_the_raw_host_preloads_every_asset_the_fragment_needs(component):
    page = _open_raw_admin_host(component)

    _assert_sheets_parsed(page, INVITE_ASSETS)
    # The swap target starts empty, so the host carried the assets itself.
    assert page.locator("#invite-dialog link, #invite-dialog script").count() == 0


def test_a_raw_host_swap_styles_the_returned_fragment(component):
    page = _open_raw_admin_host(component)
    before = _parsed_sheets(page)

    _swap_invite_fragment(page, _invite_fragment())

    dialog = page.locator(f"#invite-dialog {DIALOG}")
    assert dialog.count() == 1
    assert dialog.evaluate("dialog => dialog.open")
    assert page.get_by_role("dialog", name="Invita utente", exact=True).count() == 1
    _assert_button_is_styled(page, "#invite-dialog")
    _assert_field_is_styled(page, "#invite-dialog")
    _assert_dialog_is_styled(page, "#invite-dialog")
    # The swap added no stylesheet: everything it uses was already on the host.
    assert _parsed_sheets(page) == before


def test_repeated_swaps_keep_the_fragment_styled_and_initialized(component):
    page = _open_raw_admin_host(component)
    before = _parsed_sheets(page)
    fragment = _invite_fragment()

    for _ in range(2):
        _swap_invite_fragment(page, fragment)

        dialog = page.locator(f"#invite-dialog {DIALOG}")
        assert dialog.count() == 1
        assert dialog.evaluate("dialog => dialog.open")
        assert page.get_by_role("dialog", name="Invita utente", exact=True).count() == 1
        _assert_button_is_styled(page, "#invite-dialog")
        _assert_field_is_styled(page, "#invite-dialog")
        _assert_dialog_is_styled(page, "#invite-dialog")

        page.locator("#invite-dialog .dialog-close").click()
        assert not dialog.evaluate("dialog => dialog.open")

    assert _parsed_sheets(page) == before
