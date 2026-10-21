"""Capture or serve the two document arrangements.

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
LAYOUTS = ("a", "b")


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
        print(f"Document layout study: {server.base_url}/study", flush=True)
        print("Use the A/B buttons to switch. Ctrl+C stops this server.", flush=True)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Server stopped.", flush=True)


def capture() -> None:
    ensure_browsers_path()
    EVIDENCE.mkdir(exist_ok=True)
    captures = []

    with _server() as server:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            for profile, width, height in PROFILES:
                for layout in LAYOUTS:
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
                        f"{server.base_url}/study?layout={layout}", wait_until="load"
                    )
                    assert settle_page(page), f"{profile} {layout} did not settle"
                    assert page.evaluate(
                        "document.documentElement.scrollWidth <= innerWidth"
                    ), f"{profile} {layout} scrolls sideways"
                    path = EVIDENCE / f"{profile}-{layout}.png"
                    page.screenshot(path=path, full_page=True)
                    assert not errors, errors
                    assert not mutations, mutations
                    captures.append(
                        {
                            "profile": profile,
                            "layout": layout,
                            "viewport": {"width": width, "height": height},
                            "path": f"evidence/{path.name}",
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
