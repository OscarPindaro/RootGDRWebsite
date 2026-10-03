import re
from pathlib import Path

import pytest
from playwright.sync_api import expect

from harness.commands.compare import _PrototypeServer

pytestmark = pytest.mark.frontend
PROTOTYPE_ROOT = Path(__file__).parents[2] / "prototypes" / "devin-prototype"
ARTIFACTS = Path("/tmp/rootgdr-feedback-prototype")


@pytest.fixture(scope="module")
def prototype_url():
    with _PrototypeServer(PROTOTYPE_ROOT) as base_url:
        yield base_url + "/feedback-2026-10-03/index.html"


@pytest.fixture
def prototype_page(browser_session):
    browser = browser_session.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on(
        "console",
        lambda message: (
            errors.append(message.text) if message.type == "error" else None
        ),
    )
    yield page
    context.close()
    browser.close()
    assert not errors, errors


@pytest.mark.parametrize("width", [1440, 390])
@pytest.mark.parametrize(
    "view", ["character", "place", "session", "story", "page", "fields", "mentions"]
)
def test_feedback_prototype_views_fit_and_capture(
    prototype_page, prototype_url, width, view
):
    page = prototype_page
    page.set_viewport_size({"width": width, "height": 1000 if width == 1440 else 844})
    page.goto(f"{prototype_url}?view={view}", wait_until="networkidle")
    expect(page.get_by_role("heading", level=1)).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert page.evaluate("document.fonts.check('16px Newsreader')")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(ARTIFACTS / f"{view}-{width}.png"), full_page=True)


@pytest.mark.parametrize("layout", ["a", "b", "c"])
@pytest.mark.parametrize("view", ["story", "page"])
def test_feedback_prototype_layouts_preserve_edits(
    prototype_page, prototype_url, layout, view
):
    page = prototype_page
    page.goto(f"{prototype_url}?view={view}&layout={layout}")
    title = page.get_by_label("Titolo", exact=True)
    title.fill("Il nuovo capitolo")
    page.get_by_role("button", name="Modifica", exact=True).click()
    page.get_by_label("Testo Markdown").fill("Un testo di prova")
    page.get_by_role("button", name="Mostra il risultato").click()
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(
        path=str(ARTIFACTS / f"{view}-{layout}-desktop.png"), full_page=True
    )
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.screenshot(path=str(ARTIFACTS / f"{view}-{layout}-phone.png"), full_page=True)
    page.get_by_role("button", name="B · A margine", exact=True).click()
    expect(page.get_by_label("Titolo", exact=True)).to_have_value("Il nuovo capitolo")
    expect(page.locator(".writing-preview")).to_contain_text("Un testo di prova")


def test_feedback_prototype_actions_and_palette(prototype_page, prototype_url):
    page = prototype_page
    page.goto(f"{prototype_url}?view=session")
    today = page.evaluate("new Date().toLocaleDateString('en-CA')")
    expect(page.locator("[data-real-date]")).to_have_value(today)
    page.get_by_role("button", name="Scegli colore").click()
    page.get_by_role("button", name="Bosco", exact=True).click()
    expect(page.locator("[data-tint-name]")).to_have_text("Bosco")
    page.get_by_role("button", name="Pubblica", exact=True).click()
    expect(page.locator("[data-publication-state]")).to_have_text("Pubblicato")
    page.get_by_role("button", name="Sbloccato", exact=True).click()
    expect(page.get_by_role("button", name="Modifica", exact=True)).to_be_disabled()


def test_feedback_prototype_empty_editor_and_mentions(prototype_page, prototype_url):
    page = prototype_page
    page.goto(f"{prototype_url}?view=character")
    page.get_by_role("button", name="Aggiungi una descrizione").click()
    editor = page.get_by_label("Testo Markdown")
    editor.fill("Ho incontrato @Pa")
    expect(page.get_by_role("listbox", name="Menzioni")).to_be_visible()
    editor.press("Enter")
    expect(editor).to_have_value("Ho incontrato @[Paolo] ")
    editor.press("Control+Enter")
    expect(page.locator(".writing-preview")).to_contain_text("Ho incontrato @[Paolo]")
    page.screenshot(
        path=str(ARTIFACTS / "character-written-desktop.png"), full_page=True
    )


@pytest.mark.parametrize("width", [1440, 390])
def test_feedback_prototype_popups_fit_and_calendar_updates(
    prototype_page, prototype_url, width
):
    page = prototype_page
    page.set_viewport_size({"width": width, "height": 900})
    page.goto(f"{prototype_url}?view=character")
    page.get_by_role("button", name="Scegli colore").click()
    popup = page.locator("[data-palette]")
    expect(popup).to_be_visible()
    bounds = popup.bounding_box()
    assert bounds is not None and bounds["x"] >= 0
    assert bounds["x"] + bounds["width"] <= width
    page.screenshot(path=str(ARTIFACTS / f"palette-{width}.png"), full_page=True)
    page.keyboard.press("Escape")
    expect(popup).to_be_hidden()
    if width == 1440:
        page.goto(f"{prototype_url}?view=session")
        page.get_by_role("button", name="Apri calendario").click()
        expect(
            page.get_by_role("dialog", name="Calendario", exact=True)
        ).to_be_visible()
        page.screenshot(path=str(ARTIFACTS / "calendar-desktop.png"), full_page=True)
        page.locator('[data-calendar-date]:not([data-calendar-date=""])').first.click()
        expect(page.locator("[data-real-date]")).not_to_have_value("")
        expect(page.locator("[data-calendar]")).to_be_hidden()


def test_feedback_prototype_request_attachments_are_durable():
    requests = PROTOTYPE_ROOT.parents[1] / "docs" / "features-request"
    files = [
        path for path in requests.glob("REQ-*.md") if 2 <= int(path.name[4:8]) <= 10
    ]
    assert len(files) == 9
    attached = set()
    for path in files:
        text = path.read_text()
        assert f"id: {path.name[:8]}\n" in text
        images = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text)
        assert images, path
        for image in images:
            asset = (requests / image).resolve()
            assert asset.is_relative_to(requests)
            assert asset.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
            attached.add(asset)
        for link in re.findall(r"\]\(([^)]+\.html)(?:\?[^)]*)?\)", text):
            assert (path.parent / link).resolve().is_file(), link
    assert {asset.name[:2] for asset in attached if asset.name[:2].isdigit()} == {
        f"{number:02}" for number in range(1, 11)
    }


@pytest.mark.parametrize("width", [1440, 390])
@pytest.mark.parametrize("view", ["story", "page"])
def test_feedback_prototype_details_panel_preserves_document(
    prototype_page, prototype_url, width, view
):
    page = prototype_page
    page.set_viewport_size({"width": width, "height": 1000 if width == 1440 else 844})
    page.goto(f"{prototype_url}?view={view}", wait_until="networkidle")
    expect(page.locator('.document-toolbar[data-style="icons"]')).to_be_visible()
    page.get_by_role("button", name="Modifica", exact=True).click()
    page.get_by_label("Testo Markdown").fill("Il testo rimane nel documento.")
    page.get_by_label("Testo Markdown").evaluate("el => el.setSelectionRange(3, 9)")
    page.get_by_role("button", name="Dettagli del documento", exact=True).click()
    panel = page.get_by_role("dialog", name="Dettagli del documento", exact=True)
    expect(panel).to_be_visible()
    bounds = panel.bounding_box()
    assert bounds is not None
    assert abs(bounds["y"]) <= 1
    assert abs(bounds["x"] + bounds["width"] - width) <= 1
    if width == 390:
        assert abs(bounds["width"] - width) <= 1
        assert abs(bounds["height"] - 844) <= 1
    else:
        assert bounds["width"] < width / 2
    if view == "story":
        panel.get_by_label("Periodo", exact=True).fill("Inverno, quarto anno")
        panel.get_by_label("Stato della storia").select_option("Conclusa")
    else:
        panel.get_by_label("Indirizzo della pagina").fill("customs-and-promises")
        panel.get_by_label("Posizione nel menu").fill("7")
    panel.get_by_role("button", name="Scegli colore").click()
    panel.get_by_role("button", name="Bosco", exact=True).click()
    expect(panel.locator("[data-tint-name]")).to_have_text("Bosco")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(ARTIFACTS / f"{view}-details-{width}.png"))
    panel.get_by_role("button", name="Torna al documento", exact=True).click()
    expect(panel).to_be_hidden()
    expect(
        page.get_by_role("button", name="Dettagli del documento", exact=True)
    ).to_be_focused()
    expect(page.get_by_label("Testo Markdown")).to_have_value(
        "Il testo rimane nel documento."
    )
    assert page.get_by_label("Testo Markdown").evaluate(
        "el => [el.selectionStart, el.selectionEnd]"
    ) == [3, 9]
    expect(page.locator("[data-details-summary]")).to_contain_text(
        "Conclusa" if view == "story" else "Posizione 7"
    )
    page.get_by_role("button", name="Dettagli del documento", exact=True).click()
    expect(
        panel.get_by_label(
            "Periodo" if view == "story" else "Indirizzo della pagina", exact=True
        )
    ).to_have_value(
        "Inverno, quarto anno" if view == "story" else "customs-and-promises"
    )
    page.keyboard.press("Escape")
    expect(panel).to_be_hidden()


def test_feedback_prototype_details_sessions_and_escape(prototype_page, prototype_url):
    page = prototype_page
    page.goto(f"{prototype_url}?view=story")
    page.get_by_role("button", name="Dettagli del documento", exact=True).click()
    panel = page.get_by_role("dialog", name="Dettagli del documento", exact=True)
    panel.get_by_role("button", name="Scegli colore").click()
    page.keyboard.press("Escape")
    expect(panel).to_be_visible()
    expect(panel.locator("[data-palette]")).to_be_hidden()
    panel.get_by_role("button", name="Gestisci").click()
    sessions = page.get_by_role("dialog", name="Sessioni collegate", exact=True)
    sessions.get_by_role("checkbox", name="Le voci del mercato").check()
    sessions.get_by_role("button", name="Applica selezione").click()
    expect(panel).to_be_visible()
    expect(panel).to_contain_text("Le voci del mercato")
    panel.get_by_role("button", name="Chiudi dettagli", exact=True).click()
    expect(page.locator("[data-details-summary]")).to_contain_text("3 sessioni")


def test_feedback_prototype_locked_details_are_readonly(prototype_page, prototype_url):
    page = prototype_page
    page.goto(f"{prototype_url}?view=page")
    page.get_by_role("button", name="Sbloccato", exact=True).click()
    page.get_by_role("button", name="Dettagli del documento", exact=True).click()
    panel = page.get_by_role("dialog", name="Dettagli del documento", exact=True)
    expect(panel.get_by_label("Indirizzo della pagina")).to_be_disabled()
    expect(panel.get_by_label("Posizione nel menu")).to_be_disabled()
    expect(panel.get_by_role("button", name="Scegli colore")).to_be_disabled()
