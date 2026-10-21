"""Real-component interactions for the database-free planning study."""

import pytest
from playwright.sync_api import expect

from backend.showcase.planning import planning_study

pytestmark = pytest.mark.frontend


def mount(component, view="story"):
    return component.mount(
        "pages.showcase.Planning",
        props={"study": planning_study(view)},
        htmx=True,
    )


def test_open_and_flip_share_tracks_without_saving(component):
    page = mount(component)
    track = page.get_by_role("checkbox", name="Ada, Fatica, casella 2", exact=True)
    track.check()
    page.get_by_role("button", name="Carta fronte / retro", exact=True).click()
    card = page.locator('[data-npc="ada"]')
    expect(card.locator("[data-card-back]")).to_be_hidden()
    card.get_by_role("button", name="Gira scheda", exact=True).click()
    expect(track).to_be_checked()
    track.uncheck()
    expect(card.locator("[data-card-back]")).to_be_visible()
    expect(card.get_by_role("button", name="Torna al fronte")).to_be_visible()
    page.get_by_role("button", name="Scheda aperta", exact=True).click()
    expect(track).not_to_be_checked()
    assert not [
        request for request in component.requests() if request[0] not in {"GET", "HEAD"}
    ]


def test_image_modification_does_not_flip_and_returns_focus(component):
    page = mount(component)
    page.get_by_role("button", name="Carta fronte / retro", exact=True).click()
    image = page.get_by_role("button", name="Modifica immagine di Ada", exact=True)
    image.click()
    expect(page.locator("#planning-image")).to_be_visible()
    expect(page.locator('[data-npc="ada"]')).to_have_attribute("data-face", "front")
    page.keyboard.press("Escape")
    expect(image).to_be_focused()


def test_resolution_is_local_and_requires_an_account(component):
    page = mount(component)
    page.get_by_role("button", name="Prova una risoluzione").click()
    page.get_by_label("Risoluzione e conseguenze", exact=True).fill(
        "Esempio: gli uffici concordano un permesso provvisorio."
    )
    page.get_by_role("button", name="Mostra la risoluzione di prova").click()
    expect(page.locator("[data-conflict-status]")).to_have_text("Risolto")
    expect(page.locator("[data-resolution-text]")).to_contain_text("permesso")
    page.reload()
    expect(page.locator("[data-conflict-status]")).to_have_text("Attivo")
    expect(page.locator("[data-resolution]")).to_be_hidden()


@pytest.mark.parametrize("width", [320, 390, 901, 1440])
def test_real_shell_and_cards_do_not_overflow(component, width):
    page = mount(component, "npcs")
    page.set_viewport_size({"width": width, "height": 900})
    expect(page.get_by_role("heading", level=1)).to_have_count(1)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    page.get_by_role("button", name="Carta fronte / retro", exact=True).click()
    page.locator('[data-npc="ada"]').get_by_role("button", name="Gira scheda").click()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


@pytest.mark.parametrize("view", ["places", "character", "session"])
@pytest.mark.parametrize("width", [320, 390, 901, 1440])
def test_reference_views_reflow(component, view, width):
    page = mount(component, view)
    page.set_viewport_size({"width": width, "height": 900})
    expect(page.get_by_role("heading", level=1)).to_have_count(1)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_character_reputation_is_bounded_and_tracks_are_local(component):
    page = mount(component, "character")
    increase = page.get_by_role("button", name="Aumenta reputazione con Abitanti")
    for _ in range(5):
        increase.click()
    expect(page.locator("[data-reputation-value]").first).to_have_text("3")
    page.get_by_role("checkbox", name="Neri, Ferite, casella 1", exact=True).check()
    page.get_by_role("button", name="Prova il download del playbook").click()
    expect(page.locator("#planning-playbook-dialog")).to_be_visible()
    page.keyboard.press("Escape")
    page.reload()
    expect(page.locator("[data-reputation-value]").first).to_have_text("0")
    expect(
        page.get_by_role("checkbox", name="Neri, Ferite, casella 1", exact=True)
    ).not_to_be_checked()
