"""One real character list, two creation entries, three collection states.

The study renders the application's own ``pages.characters.CharacterList``
through the real catalog and serves the raw full pages on the ephemeral
component server. Option B is the implemented entry: the product's own script
moves the single button above the grid below 700px and the component's
stylesheet gives it a compact action row. Option A is the pre-implementation
arrangement, reproduced by the study: the same button back inside the grid with
the card geometry the prototype restates. Both options read the same cards,
drafts and button.

The test measures what the decision turned on: the first real card's offset, the
scroll needed to reveal the creation entry and its empty-collection hint, the
tap-target box, the actions above the collection, keyboard reach and horizontal
overflow. Every write control is inert and the page states that its saves are
simulated.
"""

import importlib.util
import re
import signal
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.frontend

STUDY = Path(__file__).parents[2] / "prototypes" / "collection-create-study"
SIZES = ("empty", "short", "long")


def _load_study():
    spec = importlib.util.spec_from_file_location(
        "collection_create_study", STUDY / "study.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


STUDY_MODULE = _load_study()
PAGES = {f"/study/{key}": STUDY_MODULE.render_page(key) for key in SIZES}


def _open(component, key="short", width=1440, height=1000, entry=None):
    """Serve one collection state and open it on the ephemeral server."""
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

    def fulfill(route):
        path = urlsplit(route.request.url).path
        if path not in PAGES:
            route.fulfill(status=404, body="not found", content_type="text/plain")
            return
        route.fulfill(
            status=200,
            content_type="text/html; charset=utf-8",
            body=PAGES[path],
        )

    page.route("**/study/*", fulfill)
    page.set_viewport_size({"width": width, "height": height})
    page.goto(f"{base}/study/{key}?entry={entry or 'a'}", wait_until="load")
    page.evaluate("document.fonts.ready")
    return page, failed


def _measure(page):
    return page.evaluate(STUDY_MODULE.MEASURE_JS)


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
        "/static/components/editorial/EntityCard.css",
        "/static/components/editorial/CollectionCreate.css",
        "/static/components/editorial/Collection.css",
        "/static/components/common/Grid.css",
        "/static/components/editorial/Masthead.css",
    ):
        href = next((url for url in rules if url.endswith(asset)), None)
        assert href is not None, f"{asset} was never loaded: {sorted(rules)}"
        assert rules[href] > 0, f"{asset} loaded but parsed to no rules"

    assert "Newsreader" in page.locator("h1").evaluate(
        "el => getComputedStyle(el).fontFamily"
    )
    assert (
        page.locator(".container > .grid").evaluate(
            "el => getComputedStyle(el).display"
        )
        == "grid"
    )


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
            const create = document.querySelector('[data-testid="create-character"]');
            return {
                names: texts('.container > .grid > .entity-card .entity-card__name'),
                titles: texts('.container > .grid > .entity-card .entity-card__title'),
                owners: texts('.container > .grid > .entity-card .entity-card__owner'),
                drafts: texts('.section .entity-card .entity-card__name'),
                eyebrow: text('.masthead .eyebrow'),
                create_label: text('.collection-create__label'),
                create_hint: text('.collection-create__hint'),
                create_action: create ? create.getAttribute('hx-post') : null,
            };
        }"""
    )


def _choose_b(page):
    page.get_by_role("button", name="B · Azione sopra il reticolo", exact=True).click()
    expect(page.locator("body")).to_have_attribute("data-study-entry", "b")


def _tabs_to_create(page, limit=90):
    """Count the Tab presses from the page start to the creation entry."""
    for count in range(1, limit + 1):
        page.keyboard.press("Tab")
        if page.evaluate(
            "() => document.activeElement?.dataset.testid === 'create-character'"
        ):
            return count
    raise AssertionError(f"the creation entry was not reached in {limit} tabs")


def _read_serve_url(process):
    found = {}
    lines = []

    def read():
        for line in process.stdout:
            lines.append(line)
            match = re.search(r"http://127\.0\.0\.1:\d+/study/empty", line)
            if match:
                found["url"] = match.group(0)
                return

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    reader.join(timeout=15)
    assert "url" in found, f"serve mode did not print a URL: {lines}"
    return found["url"]


def test_the_study_is_the_raw_page_with_its_real_assets(component):
    page, failed = _open(component, "short")

    assert page.evaluate("document.doctype && document.doctype.name") == "html"
    assert page.locator("html").count() == 1
    assert page.locator("body > .study-bar").count() == 1
    assert page.locator("body > .shell").count() == 1
    assert page.locator(".shell .shell").count() == 0
    assert page.locator(".rail").count() == 1
    assert page.locator(".masthead").count() == 1
    _assert_real_assets(page)
    assert not failed


@pytest.mark.parametrize("key", SIZES)
def test_both_entries_render_the_same_collection(component, key):
    page, _ = _open(component, key, width=390, height=844)
    before = _snapshot(page)
    create = page.locator('[data-testid="create-character"]').element_handle()

    _choose_b(page)

    assert _snapshot(page) == before
    assert page.evaluate(
        "(element) => element.isConnected && element === "
        "document.querySelector('[data-testid=\"create-character\"]')",
        create,
    )
    assert before["create_action"] == (
        f"/worlds/{STUDY_MODULE.WORLD_ID}/characters/new"
    )
    published = {size: count for size, count, _ in STUDY_MODULE.SIZES}
    drafts = {size: count for size, _, count in STUDY_MODULE.SIZES}
    assert len(before["names"]) == published[key]
    assert len(before["drafts"]) == drafts[key]


def test_the_pre_implementation_card_closes_the_grid(component):
    page, _ = _open(component, "long", width=390, height=844, entry="a")

    create = page.locator('[data-testid="create-character"]')
    assert create.evaluate("el => el.parentElement.className") == "grid grid-auto"
    assert create.evaluate("el => el === el.parentElement.lastElementChild")
    # The card geometry is the prototype's reproduction, not a product state.
    assert (
        create.evaluate(
            "el => getComputedStyle(el.querySelector('.collection-create__media'))"
            ".aspectRatio"
        )
        != "auto"
    )
    measured = _measure(page)
    assert measured["cards"] == 30
    assert measured["drafts"] == 3
    assert measured["create_above_first_card"] is False


def test_the_compact_entry_precedes_the_grid_on_a_phone(component):
    page, _ = _open(component, "long", width=390, height=844, entry="b")

    create = page.locator('[data-testid="create-character"]')
    assert create.evaluate("el => el.parentElement.className") == "container"
    assert create.evaluate("el => el.nextElementSibling.classList.contains('grid')")
    # B is the implemented entry: the product's script marked the move and the
    # component's own stylesheet supplies the row.
    assert create.evaluate("el => el.hasAttribute('data-collection-action')")
    assert create.evaluate("el => getComputedStyle(el).display") == "flex"
    measured = _measure(page)
    assert measured["create_above_first_card"] is True
    assert measured["create_parent"] == "container"


def test_the_compact_entry_is_phone_only(component):
    page, _ = _open(component, "long", width=1440, height=1000, entry="b")

    create = page.locator('[data-testid="create-character"]')
    assert create.evaluate("el => el.parentElement.className") == "grid grid-auto"
    assert create.evaluate("el => el === el.parentElement.lastElementChild")
    assert _measure(page)["create_above_first_card"] is False


def test_the_long_collection_is_reachable_at_the_top_of_the_phone_page(component):
    page, _ = _open(component, "long", width=390, height=844, entry="a")
    pre_implementation = _measure(page)
    page, _ = _open(component, "long", width=390, height=844, entry="b")
    compact = _measure(page)

    # A leaves the entry after 30 cards and 3 drafts; the implemented B keeps
    # it in the first screen.
    assert pre_implementation["create_reveal"] > 3000
    assert compact["create_reveal"] == 0
    # B costs the first real card the height of its action row, but the card
    # still starts inside the first phone screen.
    assert compact["first_card_top"] > pre_implementation["first_card_top"]
    assert compact["first_card_top"] - pre_implementation["first_card_top"] < 200
    assert compact["first_card_top"] < 844
    # One more action competes at the top of the phone page, and no more.
    assert compact["header_actions"] == pre_implementation["header_actions"]
    assert compact["top_actions"] == pre_implementation["top_actions"] + 1


def test_an_empty_collection_still_explains_itself_in_both_entries(component):
    page, _ = _open(component, "empty", width=390, height=844, entry="a")
    pre_implementation = _measure(page)
    hint = page.locator(".collection-create__hint")
    assert "Nessun personaggio" in hint.inner_text()
    assert pre_implementation["cards"] == 0
    # The pre-implementation card is a full empty cell, and at 390x844 its
    # hint sits below the first screen.
    assert pre_implementation["create_height"] > 400
    assert pre_implementation["hint_reveal"] > 100

    page, _ = _open(component, "empty", width=390, height=844, entry="b")
    compact = _measure(page)
    hint = page.locator(".collection-create__hint")
    assert "Nessun personaggio" in hint.inner_text()
    assert compact["create_height"] < 120
    assert compact["hint_reveal"] == 0
    # With no cards both entries are the only action above the collection.
    assert compact["top_actions"] == pre_implementation["top_actions"]


@pytest.mark.parametrize("key", SIZES)
@pytest.mark.parametrize("entry", ("a", "b"))
def test_each_entry_is_at_least_a_44px_tap_target(component, key, entry):
    page, _ = _open(component, key, width=390, height=844, entry=entry)

    measured = _measure(page)
    assert measured["create_width"] >= 44
    assert measured["create_height"] >= 44


@pytest.mark.parametrize("width", (320, 390))
@pytest.mark.parametrize("key", SIZES)
@pytest.mark.parametrize("entry", ("a", "b"))
def test_no_horizontal_overflow_at_phone_widths(component, width, key, entry):
    page, failed = _open(
        component, key, width=width, height=700 if width == 320 else 844, entry=entry
    )

    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert _measure(page)["horizontal_overflow"] is False
    assert not failed


def test_keyboard_reaches_the_create_entry_sooner_in_b(component):
    page, _ = _open(component, "long", width=390, height=844, entry="a")
    pre_implementation = _tabs_to_create(page)
    create = page.locator('[data-testid="create-character"]')
    assert create.evaluate("el => getComputedStyle(el).outlineStyle") != "none"
    assert create.evaluate("el => getComputedStyle(el).outlineWidth") != "0px"

    page, _ = _open(component, "long", width=390, height=844, entry="b")
    compact = _tabs_to_create(page)
    create = page.locator('[data-testid="create-character"]')
    assert create.evaluate("el => getComputedStyle(el).outlineStyle") != "none"

    page.keyboard.press("Enter")
    expect(page.locator("[data-study-status]")).to_contain_text("simulato")
    assert not [
        request
        for request in component.requests()
        if request[0] not in {"GET", "HEAD", "OPTIONS"}
    ]

    assert compact < pre_implementation


def test_the_comparison_and_the_simulated_boundary_are_labelled(component):
    page, _ = _open(component)
    bar = page.get_by_role("region", name="Confronto prototipo")

    expect(bar).to_contain_text("Prototipo")
    expect(bar).to_contain_text("salvataggi simulati e disattivati")
    expect(bar).to_contain_text("Nessuna modifica viene registrata")
    expect(bar).to_contain_text("Confronto, non impostazione del prodotto")

    first = page.get_by_role("button", name="A · Scheda nel reticolo", exact=True)
    second = page.get_by_role("button", name="B · Azione sopra il reticolo", exact=True)
    assert first.get_attribute("aria-pressed") == "true"
    assert second.get_attribute("aria-pressed") == "false"
    for key in SIZES:
        assert (
            bar.locator(f'[data-study-size-link="{key}"]').get_attribute("href")
            == f"/study/{key}"
        )

    _choose_b(page)

    assert first.get_attribute("aria-pressed") == "false"
    assert second.get_attribute("aria-pressed") == "true"
    expect(page.locator("[data-study-status]")).to_contain_text("Opzione B")


def test_write_controls_are_inert_and_no_write_reaches_the_server(component):
    page, _ = _open(component, "short", width=390, height=844)

    create = page.locator('[data-testid="create-character"]')
    assert create.get_attribute("aria-disabled") == "true"
    assert create.get_attribute("data-prototype-inert") == "true"
    assert create.get_attribute("title") == "Prototipo: salvataggio disattivato"

    report = page.locator('[data-dialog-open="report-panel"]').first
    assert report.is_disabled()
    assert report.get_attribute("data-prototype-inert") == "true"

    logout = page.locator('a[href="/auth/logout-view"]')
    assert logout.get_attribute("aria-disabled") == "true"
    assert logout.get_attribute("tabindex") == "-1"

    before = page.url
    create.click(force=True)
    assert page.url == before
    assert page.locator("dialog[open]").count() == 0
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
        assert 'data-study-size="empty"' in page
        assert "Personaggi" in page

        with urllib.request.urlopen(
            url.replace("/study/empty", "/study/long"), timeout=10
        ) as response:
            long_page = response.read().decode()
            long_status = response.status
        assert long_status == 200
        assert STUDY_MODULE.LONG_NAME in long_page

        with urllib.request.urlopen(
            url.replace("/study/empty", "/static/css/main.css"), timeout=10
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
