"""Shared browser lifecycle for the component test session.

Chromium is launched once per pytest session and reused; each test gets a
fresh browser context, so storage and network state never leak between tests.
"""

from playwright.sync_api import Browser, Playwright

from .session import ComponentSession

_browser: Browser | None = None


def launch(playwright: Playwright, components_dir) -> ComponentSession:
    global _browser
    if _browser is None:
        _browser = playwright.chromium.launch(headless=True)
    return ComponentSession(_browser, components_dir)


def shutdown() -> None:
    global _browser
    if _browser is not None:
        _browser.close()
        _browser = None
