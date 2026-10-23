"""Capture or serve the two phone appearance arrangements.

The page comes from the real catalog and is served on the ephemeral component
server; no application, database, work or showcase environment is involved.
``--serve`` prints the URL and waits for Ctrl+C without writing evidence.
"""

import argparse
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness.browser_runtime import ensure_browsers_path
from harness.frontend.server import ComponentServer
from harness.test.browser import settle_page

import study

HERE = Path(__file__).parent
EVIDENCE = HERE / "evidence"
PROFILES = (("desktop", 1440, 1000), ("phone", 390, 844))
STATES = (
    ("a", "always", False),
    ("b", "disclosure", False),
    ("b-open", "disclosure", True),
)
TOUCH_TARGET = 44

_MEASURE = """() => {
    const visible = (element) => {
        if (!element) return false;
        const box = element.getBoundingClientRect();
        const style = getComputedStyle(element);
        return box.width > 0 && box.height > 0
            && style.visibility !== 'hidden' && style.display !== 'none';
    };
    const box = (element) => {
        if (!element) return null;
        const rect = element.getBoundingClientRect();
        return {
            width: Math.round(rect.width),
            height: Math.round(rect.height),
            top: Math.round(rect.top + scrollY),
        };
    };
    const heading = document.querySelector('.docidentity h1');
    const documentTop = document.querySelector('.document');
    const main = document.querySelector('#main');
    const headingTop = heading.getBoundingClientRect().top + scrollY;
    const controls = [...document.querySelectorAll(
        '[data-image-surface], [data-image-history-open], '
        + '[data-image-choices] .choice-grid__option, '
        + '[data-image-disclosure], [data-study-disclosure]'
    )].filter(element =>
        visible(element)
        && (heading.compareDocumentPosition(element)
            & Node.DOCUMENT_POSITION_PRECEDING)
    );
    const disclosure = [
        document.querySelector('[data-image-disclosure]'),
        document.querySelector('[data-study-disclosure]'),
    ].filter(Boolean).find(visible);
    return {
        identityOffset: Math.round(
            headingTop
            - (documentTop.getBoundingClientRect().top + scrollY)
        ),
        identityFromMain: Math.round(
            headingTop - (main.getBoundingClientRect().top + scrollY)
        ),
        identityPageTop: Math.round(headingTop),
        visibleControlsBefore: controls.length,
        surface: box(document.querySelector('[data-image-surface]')),
        disclosure: box(disclosure),
        history: box(document.querySelector('[data-image-history-open]')),
        choicesVisible: visible(
            document.querySelector('[data-image-choices] .choice-grid')
        ),
        scrollWidth: document.documentElement.scrollWidth,
        innerWidth: innerWidth,
    };
}"""

_IDENTIFY_ACTIVE = """() => {
    const element = document.activeElement;
    const face = document.querySelector('.document__face--editor');
    if (!element || !face.contains(element)) return null;
    if (element.matches('[data-image-surface]')) return 'surface';
    if (element.matches('[data-image-disclosure], [data-study-disclosure]')) {
        return 'disclosure';
    }
    if (element.matches('[data-image-history-open]')) return 'history';
    const grid = element.closest('.choice-grid');
    if (grid) {
        return grid.classList.contains('choice-grid--emoji') ? 'animal' : 'tint';
    }
    return 'other:' + element.tagName;
}"""


def _server() -> ComponentServer:
    server = ComponentServer(
        static_dir=study.REPO / "src/frontend/static",
        components_dir=study.COMPONENTS,
    )
    server.mount_page("/study", study.render_page())
    return server


def serve() -> None:
    """Serve the study on the ephemeral server until Ctrl+C."""
    with _server() as server:
        print(f"Phone appearance study: {server.base_url}/study", flush=True)
        print(
            "Use the A/B buttons to switch and Aspetto to open the disclosure. "
            "Ctrl+C stops this server.",
            flush=True,
        )
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Server stopped.", flush=True)


def _focus_order(page) -> list[str]:
    page.locator("[data-image-surface]").focus()
    order = []
    for _ in range(10):
        identified = page.evaluate(_IDENTIFY_ACTIVE)
        if identified is None:
            break
        order.append(identified)
        page.keyboard.press("Tab")
    return order


def capture() -> None:
    ensure_browsers_path()
    EVIDENCE.mkdir(exist_ok=True)
    captures = []

    with _server() as server:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            for profile, width, height in PROFILES:
                for name, appearance, expanded in STATES:
                    if width > 700 and expanded:
                        continue
                    context = browser.new_context(
                        viewport={"width": width, "height": height},
                        reduced_motion="reduce",
                    )
                    page = context.new_page()
                    errors, mutations = [], []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.on(
                        "console",
                        lambda message: (
                            errors.append(message.text)
                            if message.type == "error"
                            else None
                        ),
                    )
                    page.on(
                        "request",
                        lambda request: (
                            mutations.append(request.url)
                            if request.method not in {"GET", "HEAD", "OPTIONS"}
                            else None
                        ),
                    )
                    query = f"?appearance={appearance}"
                    if expanded:
                        query += "&open=1"
                    page.goto(f"{server.base_url}/study{query}", wait_until="load")
                    assert settle_page(page), f"{profile} {name} did not settle"
                    assert page.evaluate(
                        "document.documentElement.scrollWidth <= innerWidth"
                    ), f"{profile} {name} scrolls sideways"
                    measurement = page.evaluate(_MEASURE)
                    if width <= 700:
                        for target in ("surface", "disclosure", "history"):
                            box = measurement[target]
                            if box and box["width"] > 0:
                                assert box["width"] >= TOUCH_TARGET, (
                                    name,
                                    target,
                                    box,
                                )
                                assert box["height"] >= TOUCH_TARGET, (
                                    name,
                                    target,
                                    box,
                                )
                    measurement["focusOrder"] = _focus_order(page)
                    # Playwright's full-page capture paints the sticky topbar
                    # at the last scroll tile, over the document. The geometry
                    # above is already measured; neutralise only that paint
                    # position so the evidence shows the document, not the
                    # capture artifact. This is not a product rule.
                    page.add_style_tag(
                        content=".topbar { position: static !important; }"
                    )
                    path = EVIDENCE / f"{profile}-{name}.png"
                    page.screenshot(path=path, full_page=True)
                    assert not errors, errors
                    assert not mutations, mutations
                    captures.append(
                        {
                            "profile": profile,
                            "state": name,
                            "appearance": appearance,
                            "expanded": expanded,
                            "viewport": {"width": width, "height": height},
                            "path": f"evidence/{path.name}",
                            "measurement": measurement,
                        }
                    )
                    context.close()
            browser.close()

    assert not [
        request
        for request in server.requests
        if request[0] not in {"GET", "HEAD", "OPTIONS"}
    ], server.requests

    record = study.revisions()
    record["captures"] = captures
    (EVIDENCE / "revisions.json").write_text(json.dumps(record, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--serve",
        action="store_true",
        help="serve the study until Ctrl+C instead of capturing evidence",
    )
    args = parser.parse_args()
    if args.serve:
        serve()
    else:
        capture()


if __name__ == "__main__":
    main()
