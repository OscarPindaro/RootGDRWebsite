"""Component tests for ``common.Dialog`` and ``common.ConfirmDialog``.

The dialog is a native ``<dialog>`` shown with ``showModal()``: the browser
traps focus and closes on Escape. The colocated script adds what the element
does not do itself — remembering the opening control and returning focus to it,
and exposing pending/error state for requests. ``ConfirmDialog`` composes it
with one named action and carries no domain knowledge.
"""

from pathlib import Path

import pytest

from backend.jinja import get_catalog

pytestmark = pytest.mark.frontend

COMPONENTS = Path(__file__).parents[2] / "src" / "frontend" / "components"


def _add_trigger(page, dialog_id: str) -> None:
    """Put a real opener in the page and click it."""
    page.evaluate(
        """id => {
            const trigger = document.createElement('button');
            trigger.id = 'opener';
            trigger.dataset.dialogOpen = id;
            trigger.textContent = 'Apri';
            document.body.prepend(trigger);
        }""",
        dialog_id,
    )
    page.click("#opener")


def _dialog(page):
    return page.locator("dialog[data-dialog]")


def _dispatch(page, name: str, selector: str, **detail) -> None:
    page.evaluate(
        """([name, selector, detail]) => {
            const elt = document.querySelector(selector);
            elt.dispatchEvent(new CustomEvent(name, {bubbles: true, detail: Object.assign({elt}, detail)}));
        }""",
        [name, selector, detail],
    )


def test_focus_enters_the_dialog_and_returns_to_the_opener_on_cancel(component):
    page = component.mount(
        "common.Dialog", props={"title": "Titolo", "id": "d1"}, content="<p>Corpo</p>"
    )
    _add_trigger(page, "d1")

    assert _dialog(page).evaluate("dialog => dialog.open")
    assert page.evaluate("() => Boolean(document.activeElement.closest('dialog'))")

    page.click("[data-dialog-close]")

    assert not _dialog(page).evaluate("dialog => dialog.open")
    assert page.evaluate("() => document.activeElement.id === 'opener'")


def test_escape_closes_and_returns_focus(component):
    page = component.mount("common.Dialog", props={"title": "Titolo", "id": "d2"})
    _add_trigger(page, "d2")

    page.keyboard.press("Escape")

    assert not _dialog(page).evaluate("dialog => dialog.open")
    assert page.evaluate("() => document.activeElement.id === 'opener'")


def test_a_dialog_without_an_id_is_named_by_its_title(component):
    page = component.mount("common.Dialog", props={"title": "Titolo"})
    dialog = _dialog(page)
    assert dialog.get_attribute("aria-labelledby") is None

    page.evaluate("() => document.querySelector('dialog[data-dialog]').showModal()")

    assert page.get_by_role("dialog", name="Titolo", exact=True).count() == 1


def test_an_explicit_id_still_names_the_dialog_through_its_heading(component):
    page = component.mount("common.Dialog", props={"title": "Titolo", "id": "d7"})
    dialog = _dialog(page)
    assert dialog.get_attribute("aria-labelledby") == "d7-title"
    assert dialog.get_attribute("aria-label") is None

    _add_trigger(page, "d7")

    assert page.locator("#d7-title").count() == 1
    assert page.get_by_role("dialog", name="Titolo", exact=True).count() == 1


def test_a_caller_label_wins_over_the_title_fallback(component):
    page = component.mount(
        "common.Dialog", props={"title": "Titolo", "aria_label": "Etichetta"}
    )

    assert _dialog(page).get_attribute("aria-label") == "Etichetta"
    assert page.content().count('aria-label="Etichetta"') == 1


def test_multiple_unnamed_dialogs_are_each_named_by_their_own_title(component):
    catalog = get_catalog(str(COMPONENTS), env="dev", app_name="harness-frontend")
    page = component.mount("common.Dialog", props={"title": "Primo"})
    page.set_content(
        str(catalog.render("common.Dialog", title="Invita utente"))
        + str(catalog.render("common.Dialog", title="Revoca invito"))
    )
    dialogs = page.locator("dialog[data-dialog]")

    assert dialogs.count() == 2
    assert page.locator("dialog[aria-labelledby]").count() == 0
    assert dialogs.evaluate_all(
        "els => els.map(el => el.getAttribute('aria-label'))"
    ) == ["Invita utente", "Revoca invito"]

    page.evaluate("() => document.querySelectorAll('dialog')[0].showModal()")
    assert page.get_by_role("dialog", name="Invita utente", exact=True).count() == 1
    page.evaluate("() => document.querySelectorAll('dialog')[0].close()")
    page.evaluate("() => document.querySelectorAll('dialog')[1].showModal()")
    assert page.get_by_role("dialog", name="Revoca invito", exact=True).count() == 1


def test_the_close_control_is_labelled_in_italian(component):
    page = component.mount("common.Dialog", props={"title": "Titolo"})

    close = page.locator("[data-dialog-close]")
    assert close.get_attribute("aria-label") == "Chiudi"
    assert page.locator(".tooltip[data-tooltip='Chiudi']").count() == 1


def test_a_successful_request_closes_and_returns_focus(component):
    page = component.mount(
        "common.Dialog",
        props={"title": "Titolo", "id": "d3"},
        content='<button id="confirm" data-dialog-confirm>Conferma</button>',
    )
    _add_trigger(page, "d3")

    _dispatch(page, "htmx:afterRequest", "#confirm", successful=True)

    assert not _dialog(page).evaluate("dialog => dialog.open")
    assert page.evaluate("() => document.activeElement.id === 'opener'")


def test_a_failed_request_keeps_the_dialog_open_and_shows_a_live_error(component):
    page = component.mount(
        "common.Dialog",
        props={"title": "Titolo", "id": "d4"},
        content='<button id="confirm" data-dialog-confirm>Conferma</button>',
    )
    _add_trigger(page, "d4")
    error = page.locator("[data-dialog-error]")
    assert error.get_attribute("role") == "alert"

    _dispatch(page, "htmx:responseError", "#confirm")

    assert _dialog(page).evaluate("dialog => dialog.open")
    assert error.is_visible()
    assert error.inner_text()


def test_pending_state_busies_the_dialog_and_disables_the_actions(component):
    page = component.mount(
        "common.Dialog",
        props={"title": "Titolo", "id": "d5"},
        content="<button data-dialog-confirm>Conferma</button>",
    )
    _add_trigger(page, "d5")

    page.evaluate(
        "() => window.rootGdrDialog.setPending(document.querySelector('dialog[data-dialog]'), true)"
    )

    assert _dialog(page).get_attribute("aria-busy") == "true"
    assert page.locator("[data-dialog-confirm]").is_disabled()
    assert page.locator("[data-dialog-close]").is_disabled()


def test_pending_disables_a_form_submit_inside_the_dialog(component):
    """The member and invite dialogs submit through their own form button."""
    page = component.mount(
        "common.Dialog",
        props={"title": "Invita", "id": "d6"},
        content='<form><button id="send" type="submit">Invia</button></form>',
    )
    _add_trigger(page, "d6")

    page.evaluate(
        "() => window.rootGdrDialog.setPending(document.querySelector('dialog[data-dialog]'), true)"
    )
    assert page.locator("#send").is_disabled()

    page.evaluate(
        "() => window.rootGdrDialog.setPending(document.querySelector('dialog[data-dialog]'), false)"
    )
    assert not page.locator("#send").is_disabled()


def test_a_destructive_confirmation_names_the_action(component):
    page = component.mount(
        "common.ConfirmDialog",
        props={
            "title": "Revoca invito",
            "message": "Revocare l'invito per jane@example.com? Non potrà più registrarsi.",
            "confirm_label": "Revoca",
            "cancel_label": "Annulla",
            "confirm_variant": "danger",
        },
    )

    assert page.locator(".confirm-dialog__message").inner_text().startswith("Revocare")
    confirm = page.locator("[data-dialog-confirm]")
    assert confirm.inner_text().strip() == "Revoca"
    assert "btn-danger" in confirm.get_attribute("class")
    assert page.locator("[data-dialog-autofocus]").inner_text().strip() == "Annulla"
    assert page.locator("[data-dialog-close][data-dialog-autofocus]").count() == 1


def test_the_generic_component_carries_no_admin_target_or_method(component):
    page = component.mount(
        "common.ConfirmDialog",
        props={"message": "Sicuro?", "confirm_label": "Conferma"},
    )

    html = page.content()
    assert "hx-delete" not in html
    assert "/admin" not in html
    assert "#invitations-table" not in html


def test_caller_action_attributes_land_on_the_confirm_button_only(component):
    """The request must not be inherited by the close and cancel controls."""
    page = component.mount(
        "common.ConfirmDialog",
        props={
            "message": "Sicuro?",
            "confirm_label": "Revoca",
            "hx_delete": "/admin/users/invitations/1",
            "hx_target": "#invitations-table",
            "hx_swap": "outerHTML",
        },
    )

    assert _dialog(page).get_attribute("hx-delete") is None
    confirm = page.locator("[data-dialog-confirm]")
    assert confirm.get_attribute("hx-delete") == "/admin/users/invitations/1"
    assert confirm.get_attribute("hx-target") == "#invitations-table"
