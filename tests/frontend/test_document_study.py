"""One real CharacterDetail document, two arrangements, one typed fixture.

The study renders the application's own ``pages.characters.CharacterDetail``
through the real catalog and serves that raw full page on the ephemeral
component server. The comparison strip changes only the body attribute the
prototype stylesheet reads, so the document, its data and its controls are the
same DOM in both arrangements. Every write control is inert and the page states
that its saves are simulated.
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

pytestmark = pytest.mark.frontend

STUDY = Path(__file__).parents[2] / "prototypes" / "document-layout-study"
PAGE = "/study"


def _load_study():
    spec = importlib.util.spec_from_file_location(
        "document_layout_study", STUDY / "study.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


STUDY_MODULE = _load_study()
PAGE_HTML = STUDY_MODULE.render_page()


def _open(component, width=1440, height=1000, layout=None):
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
    page.goto(f"{base}{PAGE}?layout={layout or 'a'}", wait_until="load")
    page.evaluate("document.fonts.ready")
    return page, failed


def _token(page, name):
    return page.evaluate(
        "name => getComputedStyle(document.documentElement)"
        ".getPropertyValue(name).trim()",
        name,
    )


def _parsed_sheets(page):
    sheets = page.evaluate(
        """() => [...document.styleSheets].map(sheet => ({
            href: sheet.href || '',
            rules: (() => { try { return sheet.cssRules.length } catch { return -1 } })(),
        }))"""
    )
    return {sheet["href"]: sheet["rules"] for sheet in sheets}


def _assert_real_assets(page):
    rules = _parsed_sheets(page)
    for asset in (
        "/static/css/main.css",
        "/static/components/editorial/Document.css",
        "/static/components/editorial/ImageEditor.css",
        "/static/components/editorial/DocIdentity.css",
        "/static/components/common/Button.css",
    ):
        href = next((url for url in rules if url.endswith(asset)), None)
        assert href is not None, f"{asset} was never loaded: {sorted(rules)}"
        assert rules[href] > 0, f"{asset} loaded but parsed to no rules"

    assert (
        page.locator(
            'script[src="/static/components/editorial/ImageEditor.js"]'
        ).count()
        == 1
    )
    assert "Newsreader" in page.locator("h1").evaluate(
        "el => getComputedStyle(el).fontFamily"
    )
    assert (
        page.locator(".document__head").evaluate("el => getComputedStyle(el).display")
        == "grid"
    )
    assert page.locator(".docbar .btn").first.evaluate(
        "el => getComputedStyle(el).height"
    ) == _token(page, "--button-height-sm")


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


def _geometry(page):
    return page.evaluate(
        """() => {
            const box = (selector) => {
                const element = document.querySelector(selector);
                if (!element) return null;
                const rect = element.getBoundingClientRect();
                return {
                    x: rect.x, y: rect.y, width: rect.width,
                    height: rect.height, right: rect.right, bottom: rect.bottom,
                };
            };
            return {
                head: box('.document__head'),
                face: box('.document__face--editor'),
                identity: box('.docidentity'),
                page: box('.document__page'),
                aside: box('.grid-document > aside'),
            };
        }"""
    )


def _choose_b(page):
    page.get_by_role(
        "button", name="B · Corpo sotto l'intestazione", exact=True
    ).click()
    expect(page.locator("body")).to_have_attribute("data-study-layout", "b")


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
    _assert_real_assets(page)
    assert not failed


def test_both_arrangements_share_the_same_data_and_dom(component):
    page, _ = _open(component)
    before = _snapshot(page)
    body = page.locator(".docedit__render").element_handle()

    _choose_b(page)

    assert _snapshot(page) == before
    assert page.evaluate(
        "(element) => element.isConnected && element === "
        "document.querySelector('.docedit__render')",
        body,
    )


def test_the_body_moves_from_beside_the_portrait_to_below_the_head(component):
    page, _ = _open(component)
    beside = _geometry(page)

    assert beside["page"]["x"] >= beside["face"]["right"] - 1
    assert beside["page"]["y"] < beside["face"]["bottom"]

    _choose_b(page)
    below = _geometry(page)

    assert below["page"]["x"] == pytest.approx(below["head"]["x"], abs=1)
    assert below["page"]["width"] == pytest.approx(below["head"]["width"], abs=1)
    assert below["page"]["y"] >= below["face"]["bottom"] - 1


@pytest.mark.parametrize("width", (1440, 390))
@pytest.mark.parametrize("layout", ("a", "b"))
def test_each_arrangement_fits_the_viewport(component, width, layout):
    page, failed = _open(
        component, width=width, height=1000 if width > 700 else 844, layout=layout
    )

    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    geometry = _geometry(page)
    if width <= 700:
        assert geometry["page"]["y"] >= geometry["face"]["bottom"] - 1
    assert not failed


def test_the_comparison_and_the_simulated_boundary_are_labelled(component):
    page, _ = _open(component)
    bar = page.get_by_role("region", name="Confronto prototipo")

    expect(bar).to_contain_text("Prototipo")
    expect(bar).to_contain_text("salvataggi simulati e disattivati")
    expect(bar).to_contain_text("Nessuna modifica viene registrata")
    expect(bar).to_contain_text("Confronto, non impostazione del prodotto")

    first = page.get_by_role("button", name="A · Ritratto affiancato", exact=True)
    second = page.get_by_role(
        "button", name="B · Corpo sotto l'intestazione", exact=True
    )
    assert first.get_attribute("aria-pressed") == "true"
    assert second.get_attribute("aria-pressed") == "false"

    _choose_b(page)

    assert first.get_attribute("aria-pressed") == "false"
    assert second.get_attribute("aria-pressed") == "true"
    expect(page.locator("[data-study-status]")).to_contain_text("Disposizione B")


def test_write_controls_are_inert_and_no_write_reaches_the_server(component):
    page, _ = _open(component)

    controls = page.locator('[data-prototype-inert="true"]:is(button, input, a, label)')
    assert controls.count() >= 40
    assert controls.first.get_attribute("title") == (
        "Prototipo: salvataggio disattivato"
    )
    assert page.evaluate(
        """() => [...document.querySelectorAll(
            '[data-prototype-inert="true"]:is(button, input, a, label)'
        )].every(element =>
            element.matches('a, label')
                ? element.getAttribute('aria-disabled') === 'true'
                : element.disabled === true
        )"""
    )

    edit = page.get_by_role("button", name="Modifica", exact=True)
    assert edit.is_disabled()
    edit.click(force=True)
    assert page.locator("dialog[open]").count() == 0

    assert page.locator("[data-image-input]").is_disabled()
    assert page.locator("[data-image-choices] input").first.is_disabled()
    assert page.locator("[data-image-surface]").get_attribute("aria-disabled") == "true"
    page.locator("[data-image-surface]").click(force=True)
    expect(page.locator("[data-study-status]")).to_contain_text("simulato")

    assert not [
        request
        for request in component.requests()
        if request[0] not in {"GET", "HEAD", "OPTIONS"}
    ]


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
        assert "Rugginosa" in page
        assert 'data-study-layout="a"' in page

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
