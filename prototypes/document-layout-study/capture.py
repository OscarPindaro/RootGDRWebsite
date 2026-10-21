"""Capture the two document arrangements at desktop and phone.

The page comes from the real catalog and is served on the ephemeral component
server; no application, database, work or showcase environment is involved.
"""

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

from harness.browser_runtime import ensure_browsers_path
from harness.frontend.server import ComponentServer

import study

HERE = Path(__file__).parent
EVIDENCE = HERE / "evidence"
PROFILES = (("desktop", 1440, 1000), ("phone", 390, 844))
LAYOUTS = ("a", "b")


def capture() -> None:
    ensure_browsers_path()
    EVIDENCE.mkdir(exist_ok=True)
    captures = []

    with ComponentServer(
        static_dir=study.REPO / "src/frontend/static",
        components_dir=study.COMPONENTS,
    ) as server:
        server.mount_page("/study", study.render_page())
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
                    page.evaluate("document.fonts.ready")
                    page.wait_for_timeout(400)
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


if __name__ == "__main__":
    capture()
