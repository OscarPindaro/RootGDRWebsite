"""Browser session helpers for component tests.

One ``ComponentSession`` per test: a fresh browser context (clean storage),
one ephemeral server, and helpers for the interactions component tests need.
Console and page errors are collected so the fixture can fail the test.
"""

from pathlib import Path

from playwright.sync_api import Browser, Page

from . import renderer, server


class ComponentSession:
    def __init__(self, browser: Browser, components_dir: Path) -> None:
        self._browser = browser
        self._components_dir = components_dir
        self._server = server.ComponentServer(
            static_dir=components_dir.parent / "static",
            components_dir=components_dir,
        )
        self._server.start()
        self._context = None
        self.page: Page | None = None
        self.console_errors: list[str] = []
        self.page_errors: list[str] = []
        self._routes: list[server.JsonRoute] = []

    def mount(
        self,
        component: str,
        props: dict | None = None,
        content: str = "",
        *,
        htmx: bool = False,
        reduced_motion: bool = False,
    ) -> Page:
        """Render a component with the real catalog and open it."""
        page = renderer.render_component(
            self._components_dir, component, props, content, htmx=htmx
        )
        self._server.mount_page("/", page.html)
        if self._context is not None:
            self._context.close()
        self._context = self._browser.new_context(
            reduced_motion="reduce" if reduced_motion else "no-preference"
        )
        self.console_errors = []
        self.page_errors = []
        self.page = self._context.new_page()
        self.page.on(
            "console",
            lambda message: (
                self.console_errors.append(message.text)
                if message.type == "error"
                else None
            ),
        )
        self.page.on("pageerror", lambda error: self.page_errors.append(str(error)))
        self.page.goto(f"{self._server.base_url}/")
        return self.page

    def route_json(
        self,
        method: str,
        path: str,
        *,
        status: int = 200,
        body: dict | list | None = None,
    ) -> None:
        """Register a fake API endpoint served by the ephemeral server.

        Routes accumulate, so a page that fetches several endpoints can be
        served them all.
        """
        self._routes.append(
            server.JsonRoute(method=method, path=path, status=status, body=body or {})
        )
        self._server.set_routes(self._routes)

    def requests(self) -> list[tuple[str, str]]:
        return self._server.requests

    def go_offline(self) -> None:
        assert self._context is not None
        self._context.set_offline(True)

    def go_online(self) -> None:
        assert self._context is not None
        self._context.set_offline(False)

    def click(self, test_id: str) -> None:
        self.page.click(f'[data-testid="{test_id}"]')

    def press(self, key: str) -> None:
        self.page.keyboard.press(key)

    def expect_text(self, text: str) -> None:
        self.page.wait_for_selector(f"text={text}")

    def expect_focus(self, test_id: str) -> None:
        self.page.wait_for_function(
            "id => document.activeElement?.dataset.testid === id", arg=test_id
        )

    def emit_htmx_after_swap(self, selector: str = "body") -> None:
        """Fire ``htmx:afterSwap`` so components can re-initialise after a swap."""
        self.page.evaluate(
            """selector => {
                document.querySelector(selector).dispatchEvent(
                    new CustomEvent('htmx:afterSwap', {bubbles: true})
                );
            }""",
            selector,
        )

    def local_storage(self, key: str) -> str | None:
        return self.page.evaluate(f"localStorage.getItem({key!r})")

    def set_local_storage(self, key: str, value: str) -> None:
        self.page.evaluate(f"localStorage.setItem({key!r}, {value!r})")

    def screenshot(self, path: Path) -> None:
        self.page.screenshot(path=str(path), full_page=True)

    def html(self) -> str:
        return self.page.content()

    def close(self) -> None:
        if self._context is not None:
            self._context.close()
            self._context = None
        self.page = None
        self._server.close()
