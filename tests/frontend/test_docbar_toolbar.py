"""The document bar's icon commands (REQ-0005/T01).

Icon-only commands with Italian labels, the label naming the action available
now, a labelled secondary menu for the destructive action, 44px phone targets
and keyboard reachability. The component fixture loads the real Menu.js, so the
popover opens the way it does in the application.
"""

import pytest

pytestmark = pytest.mark.frontend

BASE = "/worlds/w/characters/c"


def _mount(component, **overrides):
    props = {"base": BASE, "eyebrow": "Personaggio", "can_manage": True}
    props.update(overrides)
    return component.mount("editorial.Docbar", props=props)


def _commands(page) -> dict:
    return page.evaluate(
        """() => {
            const labels = {};
            document.querySelectorAll('.docbar__commands [aria-label]').forEach(
                (el) => { labels[el.dataset.testid || el.id || 'trigger'] =
                    el.getAttribute('aria-label'); });
            return labels;
        }"""
    )


def test_every_command_is_icon_only_with_an_italian_label(component):
    page = _mount(component)

    labels = _commands(page)
    assert labels["document-edit"] == "Modifica"
    assert labels["document-lock"] == "Blocca"
    assert labels["document-publication"] == "Riporta a bozza"
    assert labels["docbar-more-trigger"] == "Altre azioni"

    # No visible command text inside the command buttons (the menu item keeps
    # its label: the destructive action must stay readable).
    texts = page.evaluate(
        """() => [...document.querySelectorAll(
                '.docbar__commands button:not([role="menuitem"])')]
            .map((el) => el.innerText.trim())"""
    )
    assert texts == [""] * len(texts)
    assert page.locator(".docbar__commands .btn-label").count() == 0


def test_the_labels_follow_the_current_action(component):
    locked = _commands(_mount(component, locked=True, is_draft=True))
    assert locked["document-lock"] == "Sblocca"
    assert locked["document-publication"] == "Pubblica"
    assert "document-edit" not in locked


def test_the_destructive_action_lives_in_a_labelled_menu(component):
    page = _mount(component)

    trigger = page.locator("#docbar-more-trigger")
    assert trigger.get_attribute("aria-haspopup") == "menu"
    assert trigger.get_attribute("aria-expanded") == "false"
    assert page.locator("#docbar-more [role='menuitem']").count() == 0 or not (
        page.locator("#docbar-more").is_visible()
    )

    trigger.click()
    page.wait_for_selector("#docbar-more:popover-open")

    item = page.locator('#docbar-more [data-testid="document-delete"]')
    assert item.inner_text().strip() == "Elimina"
    assert "/confirm/delete" in item.get_attribute("hx-get")

    # Activating the item closes the menu and hands over to the confirmation.
    item.click()
    page.wait_for_function(
        "() => !document.querySelector('#docbar-more').matches(':popover-open')"
    )


def test_a_draft_puts_cancel_draft_in_the_menu(component):
    page = _mount(component, is_draft=True)

    page.locator("#docbar-more-trigger").click()
    page.wait_for_selector("#docbar-more:popover-open")

    item = page.locator('#docbar-more [data-testid="document-cancel-draft"]')
    assert item.inner_text().strip() == "Annulla bozza"
    assert "/confirm/cancel-draft" in item.get_attribute("hx-get")


def test_the_phone_bar_keeps_44px_targets(component):
    page = _mount(component)
    page.set_viewport_size({"width": 390, "height": 844})

    sizes = page.evaluate(
        """() => [...document.querySelectorAll('.docbar__commands .btn-icon-only')]
            .map((el) => { const box = el.getBoundingClientRect();
                return [box.width, box.height]; })"""
    )
    assert sizes, "no icon command rendered"
    for width, height in sizes:
        assert width >= 44 and height >= 44, sizes


def test_every_command_is_keyboard_reachable(component):
    page = _mount(component)

    reachable = page.evaluate(
        """() => [...document.querySelectorAll(
                '.docbar__commands button:not([role="menuitem"])')]
            .map((el) => { el.focus(); return document.activeElement === el; })"""
    )
    assert all(reachable)

    # The menu item is reachable once the menu is open, which also focuses it.
    page.locator("#docbar-more-trigger").click()
    page.wait_for_selector("#docbar-more:popover-open")
    page.wait_for_function(
        """() => document.activeElement ===
            document.querySelector('#docbar-more [role="menuitem"]')"""
    )


def test_the_commands_advertise_their_shortcuts(component):
    page = _mount(component)

    assert (
        page.locator('[data-testid="document-edit"]').get_attribute("aria-keyshortcuts")
        == "F2"
    )
    publication = page.locator('[data-testid="document-publication"]')
    assert "Control+Shift+Enter" in publication.get_attribute("aria-keyshortcuts")


def test_the_menu_opens_the_italian_shortcut_help(component):
    page = _mount(component)

    page.locator("#docbar-more-trigger").click()
    page.wait_for_selector("#docbar-more:popover-open")
    page.locator("#docbar-more [role='menuitem']", has_text="Scorciatoie").click()
    page.wait_for_selector("#docbar-shortcuts[open]")

    text = page.locator("#docbar-shortcuts").inner_text().lower()
    assert "f2" in text
    assert "ctrl" in text
    assert "pubblica" in text
    # The menu closed; the dialog owns the focus now.
    assert page.evaluate(
        "() => !document.querySelector('#docbar-more').matches(':popover-open')"
    )
