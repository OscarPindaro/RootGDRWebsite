"""One real CharacterDetail document, two phone appearance arrangements.

The study renders the application's own ``pages.characters.CharacterDetail``
through the real catalog and serves that raw full page on the ephemeral
component server. The comparison strip changes only body attributes the
prototype stylesheet reads, so the document, its data and its controls are the
same DOM in both arrangements. Every write control is inert and the page states
that its saves are simulated.

The measurements are the decision evidence: how far the identity heading sits
from the start of the document, how many appearance controls precede it, the
tab order, the touch floor and horizontal overflow at 320 and 390.
"""

import importlib.util
import re
import signal
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path

import pytest
from playwright.sync_api import expect

from backend.content.view_helpers import animal_options, tint_options

pytestmark = pytest.mark.frontend

STUDY = Path(__file__).parents[2] / "prototypes" / "appearance-study"
PAGE = "/study"
TOUCH_TARGET = 44
ANIMAL_CHOICES = 16
TINT_CHOICES = 12


def _load_study():
    spec = importlib.util.spec_from_file_location(
        "appearance_study", STUDY / "study.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


STUDY_MODULE = _load_study()
PAGE_HTML = STUDY_MODULE.render_page()


def _open(component, width=1440, height=1000, appearance=None, expanded=False):
    """Serve the raw catalog page and open it on the ephemeral server."""
    page = component.mount("common.Divider")
    base = page.url.rstrip("/")
    failed = []
    page.on(
        "response",
        lambda response: (
            failed.append((response.status, response.url))
            if response.status >= 400 and "/static/" in response.url
            else None
        ),
    )
    page.route(
        "**/study*",
        lambda route: route.fulfill(
            status=200, content_type="text/html; charset=utf-8", body=PAGE_HTML
        ),
    )
    page.set_viewport_size({"width": width, "height": height})
    query = f"?appearance={appearance or 'always'}"
    if expanded:
        query += "&open=1"
    page.goto(f"{base}{PAGE}{query}", wait_until="load")
    page.evaluate("document.fonts.ready")
    return page, failed


_MEASURE = """() => {
    const visible = (element) => {
        if (!element) return false;
        const box = element.getBoundingClientRect();
        const style = getComputedStyle(element);
        return box.width > 0 && box.height > 0
            && style.visibility !== 'hidden' && style.display !== 'none';
    };
    const box = (selector) => {
        const element = document.querySelector(selector);
        if (!element) return null;
        const rect = element.getBoundingClientRect();
        return {
            width: rect.width, height: rect.height,
            top: rect.top + scrollY, bottom: rect.bottom + scrollY,
        };
    };
    const heading = document.querySelector('.docidentity h1');
    const documentTop = document.querySelector('.document');
    const headingTop = heading.getBoundingClientRect().top + scrollY;
    const controls = [...document.querySelectorAll(
        '[data-image-surface], [data-image-history-open], '
        + '[data-image-choices] .choice-grid__option, [data-study-disclosure]'
    )].filter(element =>
        visible(element)
        && (heading.compareDocumentPosition(element)
            & Node.DOCUMENT_POSITION_PRECEDING)
    );
    return {
        identityOffset: headingTop
            - (documentTop.getBoundingClientRect().top + scrollY),
        identityPageTop: headingTop,
        visibleControlsBefore: controls.length,
        surface: box('[data-image-surface]'),
        disclosure: box('[data-study-disclosure]'),
        history: box('[data-image-history-open]'),
        choicesVisible: visible(document.querySelector('[data-image-choices]')),
        historyVisible: visible(document.querySelector('[data-image-history-open]')),
        scrollWidth: document.documentElement.scrollWidth,
        innerWidth: innerWidth,
    };
}"""


_IDENTIFY_ACTIVE = """() => {
    const element = document.activeElement;
    const face = document.querySelector('.document__face--editor');
    if (!element || !face.contains(element)) return null;
    if (element.matches('[data-image-surface]')) return 'surface';
    if (element.matches('[data-study-disclosure]')) return 'disclosure';
    if (element.matches('[data-image-history-open]')) return 'history';
    const grid = element.closest('.choice-grid');
    if (grid) {
        return grid.classList.contains('choice-grid--emoji') ? 'animal' : 'tint';
    }
    return 'other:' + element.tagName;
}"""


def _measure(page):
    return page.evaluate(_MEASURE)


def _focus_order(page):
    page.locator("[data-image-surface]").focus()
    order = []
    for _ in range(10):
        identified = page.evaluate(_IDENTIFY_ACTIVE)
        if identified is None:
            break
        order.append(identified)
        page.keyboard.press("Tab")
    return order


def _snapshot(page):
    return page.evaluate(
        """() => {
            const text = (selector) => {
                const element = document.querySelector(selector);
                return element
                    ? element.textContent.replace(/\\s+/g, ' ').trim()
                    : null;
            };
            const texts = (selector) => [...document.querySelectorAll(selector)]
                .map(element => element.textContent.replace(/\\s+/g, ' ').trim());
            return {
                name: text('.docidentity h1'),
                title: text('.docidentity__subtitle'),
                summary: text('.docsummary__render'),
                body: text('.docedit__render'),
                links: texts('.links__item'),
                choices: texts('[data-image-choices] .choice-grid__option'),
                main: text('#main'),
            };
        }"""
    )


def _choose_b(page):
    page.get_by_role("button", name="B · Dietro disclosure", exact=True).click()
    expect(page.locator("body")).to_have_attribute(
        "data-study-appearance", "disclosure"
    )


def _read_serve_url(process):
    found = {}
    lines = []

    def read():
        for line in process.stdout:
            lines.append(line)
            match = re.search(r"http://127\.0\.0\.1:\d+/study", line)
            if match:
                found["url"] = match.group(0)
                return

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    reader.join(timeout=15)
    assert "url" in found, f"serve mode did not print a URL: {lines}"
    return found["url"]


def test_the_study_is_the_raw_page_with_its_real_assets(component):
    page, failed = _open(component)

    assert page.evaluate("document.doctype && document.doctype.name") == "html"
    assert page.locator("html").count() == 1
    assert page.locator("body > .study-bar").count() == 1
    assert page.locator("body > .shell").count() == 1
    assert page.locator(".shell .shell").count() == 0
    assert page.locator(".rail").count() == 1
    assert page.locator(".document--sized .document__head").count() == 1
    assert page.locator(".document__face--editor .image-editor").count() == 1
    assert page.locator("[data-image-choices] .choice-grid__option").count() == (
        ANIMAL_CHOICES + TINT_CHOICES
    )

    rules = page.evaluate(
        """() => [...document.styleSheets].map(sheet => ({
            href: sheet.href || '',
            rules: (() => { try { return sheet.cssRules.length } catch { return -1 } })(),
        }))"""
    )
    loaded = {sheet["href"]: sheet["rules"] for sheet in rules}
    for asset in (
        "/static/css/main.css",
        "/static/components/editorial/Document.css",
        "/static/components/editorial/ImageEditor.css",
        "/static/components/editorial/DocIdentity.css",
        "/static/components/common/ChoiceGrid.css",
        "/static/components/common/Button.css",
    ):
        href = next((url for url in loaded if url.endswith(asset)), None)
        assert href is not None, f"{asset} was never loaded: {sorted(loaded)}"
        assert loaded[href] > 0, f"{asset} loaded but parsed to no rules"
    assert (
        page.locator(
            'script[src="/static/components/editorial/ImageEditor.js"]'
        ).count()
        == 1
    )
    assert "Newsreader" in page.locator("h1").evaluate(
        "el => getComputedStyle(el).fontFamily"
    )
    assert not failed


def test_both_arrangements_share_the_same_data_and_dom(component):
    page, _ = _open(component, width=390, height=844)
    before = _snapshot(page)
    heading = page.locator(".docidentity h1").element_handle()
    choices = page.locator("[data-image-choices]").element_handle()
    disclosure = page.locator("[data-study-disclosure]").element_handle()

    _choose_b(page)

    assert _snapshot(page) == before
    assert page.evaluate(
        "(element) => element.isConnected && element === "
        "document.querySelector('.docidentity h1')",
        heading,
    )
    assert page.evaluate(
        "(element) => element.isConnected && element === "
        "document.querySelector('[data-image-choices]')",
        choices,
    )
    assert page.evaluate(
        "(element) => element.isConnected && element === "
        "document.querySelector('[data-study-disclosure]')",
        disclosure,
    )
    assert page.locator("[data-study-disclosure]").get_attribute("aria-expanded") == (
        "false"
    )
    assert page.locator("[data-study-disclosure]").get_attribute("aria-controls") == (
        "study-appearance-history study-appearance-choices"
    )


def test_the_disclosure_moves_the_identity_and_hides_the_controls(component):
    page, _ = _open(component, width=390, height=844)
    always = _measure(page)
    surface_for = page.locator("[data-image-surface]").get_attribute("for")

    assert always["visibleControlsBefore"] == (ANIMAL_CHOICES + TINT_CHOICES + 2)
    assert always["choicesVisible"] is True
    assert always["historyVisible"] is True
    assert surface_for == page.locator("[data-image-input]").get_attribute("id")
    assert not page.locator("[data-study-disclosure]").is_visible()

    _choose_b(page)
    collapsed = _measure(page)

    assert collapsed["visibleControlsBefore"] == 2
    assert collapsed["choicesVisible"] is False
    assert collapsed["historyVisible"] is False
    assert always["identityOffset"] - collapsed["identityOffset"] >= 400
    assert collapsed["identityOffset"] < always["identityOffset"] / 2
    assert page.locator("[data-image-surface]").get_attribute("for") == surface_for
    assert page.locator("[data-study-disclosure]").is_visible()
    assert "Aspetto" in page.locator("[data-study-disclosure]").inner_text()

    page.locator("[data-study-disclosure]").click()
    expanded = _measure(page)

    assert page.locator("body").get_attribute("data-study-expanded") == "true"
    assert (
        page.locator("[data-study-disclosure]").get_attribute("aria-expanded") == "true"
    )
    assert expanded["visibleControlsBefore"] == (ANIMAL_CHOICES + TINT_CHOICES + 3)
    assert expanded["choicesVisible"] is True
    assert expanded["historyVisible"] is True
    assert expanded["identityOffset"] > always["identityOffset"]

    page.locator("[data-study-disclosure]").click()
    assert page.locator("body").get_attribute("data-study-expanded") == "false"
    assert _measure(page)["identityOffset"] == collapsed["identityOffset"]


@pytest.mark.parametrize("width", (320, 390))
@pytest.mark.parametrize(
    ("appearance", "expanded"),
    (("always", False), ("disclosure", False), ("disclosure", True)),
)
def test_each_arrangement_fits_the_phone(component, width, appearance, expanded):
    page, failed = _open(
        component, width=width, height=844, appearance=appearance, expanded=expanded
    )

    measurement = _measure(page)
    assert measurement["scrollWidth"] <= measurement["innerWidth"] == width
    assert measurement["surface"]["width"] >= TOUCH_TARGET
    assert measurement["surface"]["height"] >= TOUCH_TARGET
    if appearance == "disclosure":
        assert measurement["disclosure"]["width"] >= TOUCH_TARGET
        assert measurement["disclosure"]["height"] >= TOUCH_TARGET
    if expanded or appearance == "always":
        assert measurement["history"]["width"] >= TOUCH_TARGET
        assert measurement["history"]["height"] >= TOUCH_TARGET
    assert not failed


def test_the_phone_tab_order_follows_the_visible_controls(component):
    page, _ = _open(component, width=390, height=844, appearance="always")
    assert _focus_order(page) == ["surface", "history", "animal", "tint"]

    page.get_by_role("button", name="B · Dietro disclosure", exact=True).click()
    assert _focus_order(page) == ["surface", "disclosure"]

    page.locator("[data-study-disclosure]").click()
    assert _focus_order(page) == [
        "surface",
        "disclosure",
        "history",
        "animal",
        "tint",
    ]


def test_desktop_keeps_the_current_arrangement(component):
    page, _ = _open(component, width=1440, height=1000, appearance="always")
    always = _measure(page)

    assert always["visibleControlsBefore"] == (ANIMAL_CHOICES + TINT_CHOICES + 2)
    assert always["choicesVisible"] is True
    assert always["disclosure"]["width"] == 0

    _choose_b(page)
    disclosure = _measure(page)

    assert disclosure["identityOffset"] == pytest.approx(
        always["identityOffset"], abs=1
    )
    assert disclosure["visibleControlsBefore"] == always["visibleControlsBefore"]
    assert disclosure["choicesVisible"] is True
    assert disclosure["disclosure"]["width"] == 0


def test_the_comparison_and_the_simulated_boundary_are_labelled(component):
    page, _ = _open(component, width=390, height=844)
    bar = page.get_by_role("region", name="Confronto prototipo")

    expect(bar).to_contain_text("Prototipo")
    expect(bar).to_contain_text("salvataggi simulati e disattivati")
    expect(bar).to_contain_text("Nessuna modifica viene registrata")
    expect(bar).to_contain_text("Confronto, non impostazione del prodotto")
    expect(bar).to_contain_text("il desktop resta identico")

    first = page.get_by_role("button", name="A · Sempre visibili", exact=True)
    second = page.get_by_role("button", name="B · Dietro disclosure", exact=True)
    assert first.get_attribute("aria-pressed") == "true"
    assert second.get_attribute("aria-pressed") == "false"
    expect(page.locator("[data-study-metrics]")).to_contain_text("30 controlli prima")

    _choose_b(page)

    assert first.get_attribute("aria-pressed") == "false"
    assert second.get_attribute("aria-pressed") == "true"
    expect(page.locator("[data-study-status]")).to_contain_text("B · Dietro disclosure")
    expect(page.locator("[data-study-metrics]")).to_contain_text("2 controlli prima")


def test_write_controls_are_inert_and_no_write_reaches_the_server(component):
    page, _ = _open(component, width=390, height=844)

    appearance = page.locator(
        "[data-image-surface], [data-image-history-open], "
        "[data-image-choices] input, [data-image-choices] label"
    )
    assert appearance.count() >= 30
    assert page.evaluate(
        """() => [...document.querySelectorAll(
            '[data-image-surface], [data-image-history-open], '
            + '[data-image-choices] input, [data-image-choices] label'
        )].every(element =>
            element.getAttribute('data-prototype-inert') === 'true'
            && element.getAttribute('aria-disabled') === 'true'
            && element.getAttribute('title') === 'Prototipo: salvataggio disattivato'
        )"""
    )

    edit = page.get_by_role("button", name="Modifica", exact=True)
    assert edit.is_disabled()
    edit.click(force=True)
    assert page.locator("dialog[open]").count() == 0

    checked = page.evaluate(
        "() => [...document.querySelectorAll('[data-image-choices] input')]"
        ".map(input => input.checked)"
    )
    page.locator("[data-image-choices] .choice-grid--emoji .choice-grid__option").nth(
        1
    ).click(force=True)
    assert (
        page.evaluate(
            "() => [...document.querySelectorAll('[data-image-choices] input')]"
            ".map(input => input.checked)"
        )
        == checked
    )
    assert page.locator("dialog[open]").count() == 0
    expect(page.locator("[data-study-status]")).to_contain_text("simulato")

    page.locator("[data-image-surface]").click(force=True)
    assert page.locator("dialog[open]").count() == 0
    assert not [
        request
        for request in component.requests()
        if request[0] not in {"GET", "HEAD", "OPTIONS"}
    ]


def test_read_only_and_locked_characters_keep_no_appearance_controls(component):
    props = {
        "world_id": STUDY_MODULE.WORLD_ID,
        "owner_kind": "character",
        "owner_id": STUDY_MODULE.CHARACTER_ID,
        "upload_url": "/api/image",
        "fallback_action": "/worlds/w/characters/c/image",
        "image_url": None,
        "can_manage": False,
        "locked": False,
        "version": 1,
        "tint": "p8",
        "symbol": "🦊",
        "symbol_name": "animal",
        "symbol_kind": "emoji",
        "symbol_options": animal_options(),
        "tints": tint_options(),
    }
    page = component.mount("editorial.ImageEditor", props=props)

    assert page.locator(".image-editor__surface--readonly").count() == 1
    assert page.locator("[data-image-choices]").count() == 0
    assert page.locator("[data-image-history-open]").count() == 0
    assert page.locator("[data-study-disclosure]").count() == 0

    page = component.mount(
        "editorial.ImageEditor", props={**props, "locked": True, "can_manage": True}
    )
    assert page.locator(".image-editor__surface--readonly").count() == 1
    assert page.locator("[data-image-choices]").count() == 0
    assert page.locator("[data-image-history-open]").count() == 0


def test_serve_mode_prints_the_ephemeral_url_and_stops_on_ctrl_c():
    revisions = STUDY / "evidence" / "revisions.json"
    before = revisions.read_bytes()
    process = subprocess.Popen(
        [sys.executable, str(STUDY / "capture.py"), "--serve"],
        cwd=STUDY.parents[1],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        url = _read_serve_url(process)
        with urllib.request.urlopen(url, timeout=10) as response:
            page = response.read().decode()
            page_status = response.status
        assert page_status == 200
        assert "Fiamma Rossa" in page
        assert 'data-study-appearance="always"' in page

        with urllib.request.urlopen(
            url.replace("/study", "/static/css/main.css"), timeout=10
        ) as response:
            css = response.read()
            css_status = response.status
            css_type = response.headers["Content-Type"]
        assert css_status == 200
        assert css_type.startswith("text/css")
        assert css

        process.send_signal(signal.SIGINT)
        assert process.wait(timeout=10) == 0
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)

    assert revisions.read_bytes() == before
