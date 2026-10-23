"""Capture or serve the two collection creation entries.

The page comes from the real catalog and is served on the ephemeral component
server; no application, database, work or showcase environment is involved.
``--serve`` prints the URLs and waits for Ctrl+C without writing evidence.
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
ENTRIES = ("a", "b")


def _server() -> ComponentServer:
    server = ComponentServer(
        static_dir=study.REPO / "src/frontend/static",
        components_dir=study.COMPONENTS,
    )
    for key, _, _ in study.SIZES:
        server.mount_page(f"/study/{key}", study.render_page(key))
    return server


def serve() -> None:
    """Serve the study on the ephemeral server until Ctrl+C."""
    with _server() as server:
        print(f"Collection creation study: {server.base_url}/study/empty", flush=True)
        print(
            "Also /study/short and /study/long. "
            "Use the A/B buttons to switch. Ctrl+C stops this server.",
            flush=True,
        )
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Server stopped.", flush=True)


def _tabs_to_create(page, limit: int = 120) -> int | None:
    """Count the Tab presses from the page start to the creation entry."""
    for count in range(1, limit + 1):
        page.keyboard.press("Tab")
        if page.evaluate(
            "() => document.activeElement?.dataset.testid === 'create-character'"
        ):
            return count
    return None


def capture() -> None:
    ensure_browsers_path()
    EVIDENCE.mkdir(exist_ok=True)
    captures, measurements = [], []

    with _server() as server:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            for profile, width, height in PROFILES:
                for key, _, _ in study.SIZES:
                    for entry in ENTRIES:
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
                        page.goto(
                            f"{server.base_url}/study/{key}?entry={entry}",
                            wait_until="load",
                        )
                        assert settle_page(page), (
                            f"{profile} {key} {entry} did not settle"
                        )
                        measured = page.evaluate(study.MEASURE_JS)
                        assert not measured["horizontal_overflow"], (
                            f"{profile} {key} {entry} scrolls sideways"
                        )
                        path = EVIDENCE / f"{profile}-{key}-{entry}.png"
                        page.screenshot(path=path, full_page=True)
                        assert not errors, errors
                        assert not mutations, mutations
                        measured["tabs_to_create"] = _tabs_to_create(page)
                        captures.append(
                            {
                                "profile": profile,
                                "size": key,
                                "entry": entry,
                                "viewport": {"width": width, "height": height},
                                "path": f"evidence/{path.name}",
                            }
                        )
                        measurements.append(
                            {
                                "profile": profile,
                                "size": key,
                                "entry": entry,
                                **measured,
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
    (EVIDENCE / "measurements.json").write_text(
        json.dumps(measurements, indent=2) + "\n"
    )


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
