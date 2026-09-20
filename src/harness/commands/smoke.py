"""Authenticated browser smoke checks for a running development backend."""

from __future__ import annotations

from typing import Annotated, Literal

import typer
from playwright.sync_api import BrowserContext, Page
from playwright.sync_api import Error as PlaywrightError
from pydantic import BaseModel, Field
from rich.console import Console

from ..test import state
from ..test.browser import expect_api, new_authenticated_context, sync_playwright

DEFAULT_EMAIL = "e2e-admin@example.com"
MAIN_ROUTES = ("/", "/worlds", "/components")
WORLD_SECTIONS = ("characters", "npcs", "places", "pages", "sessions", "stories")

console = Console()
err_console = Console(stderr=True)


class SmokeFailure(BaseModel):
    path: str
    kind: Literal["http", "console", "page"]
    detail: str


class SmokeResult(BaseModel):
    base_url: str
    checked_paths: list[str]
    failures: list[SmokeFailure]

    @property
    def ok(self) -> bool:
        return not self.failures


class _World(BaseModel):
    id: str = Field(min_length=1)


class _WorldPage(BaseModel):
    data: list[_World]


def resolve_base_url(base_url: str | None) -> str:
    """Resolve an explicit URL or the backend in the active Docker environment."""
    if base_url is not None:
        resolved = base_url.rstrip("/")
        if not resolved.startswith(("http://", "https://")):
            raise ValueError("Base URL must start with http:// or https://")
        return resolved

    environment = state.read()
    if (
        environment is None
        or environment.mode != state.EnvironmentMode.DOCKER
        or environment.ports.backend is None
    ):
        raise RuntimeError(
            "Smoke checks require an active Docker harness environment "
            "or an explicit base URL"
        )
    return f"http://127.0.0.1:{environment.ports.backend}"


def world_routes(world_id: str) -> list[str]:
    root = f"/worlds/{world_id}"
    return [root, *(f"{root}/{section}" for section in WORLD_SECTIONS)]


def discover_world_id(context: BrowserContext, base_url: str) -> str:
    response = expect_api(context, base_url, "/api/worlds/")
    try:
        worlds = _WorldPage.model_validate(response.json()).data
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"GET /api/worlds/: invalid response: {error}") from error
    if not worlds:
        raise RuntimeError("GET /api/worlds/: no accessible world found")
    return worlds[0].id


def check_routes(page: Page, base_url: str, paths: list[str]) -> list[SmokeFailure]:
    """Visit routes and collect navigation, console, and page errors."""
    failures: list[SmokeFailure] = []
    current_path = ["<browser>"]

    def record_console(message) -> None:
        if message.type == "error":
            failures.append(
                SmokeFailure(path=current_path[0], kind="console", detail=message.text)
            )

    def record_page_error(error) -> None:
        failures.append(
            SmokeFailure(path=current_path[0], kind="page", detail=str(error))
        )

    page.on("console", record_console)
    page.on("pageerror", record_page_error)

    for path in paths:
        current_path[0] = path
        try:
            response = page.goto(f"{base_url}{path}", wait_until="networkidle")
        except PlaywrightError as error:
            failures.append(
                SmokeFailure(
                    path=path, kind="http", detail=f"navigation failed: {error}"
                )
            )
            continue
        status = response.status if response is not None else None
        if status != 200:
            failures.append(
                SmokeFailure(
                    path=path,
                    kind="http",
                    detail=f"expected 200, got {status if status is not None else 'no response'}",
                )
            )
    return failures


def check_context(context: BrowserContext, base_url: str) -> SmokeResult:
    """Run smoke checks in an already authenticated browser context."""
    paths = list(MAIN_ROUTES)
    failures: list[SmokeFailure] = []
    try:
        paths.extend(world_routes(discover_world_id(context, base_url)))
    except (AssertionError, RuntimeError) as error:
        failures.append(
            SmokeFailure(path="/api/worlds/", kind="http", detail=str(error))
        )

    failures.extend(check_routes(context.new_page(), base_url, paths))
    return SmokeResult(base_url=base_url, checked_paths=paths, failures=failures)


def run_smoke(
    *, email: str = DEFAULT_EMAIL, base_url: str | None = None
) -> SmokeResult:
    """Authenticate with dev login and run smoke checks against one backend."""
    resolved_url = resolve_base_url(base_url)
    with sync_playwright() as playwright:
        browser, context = new_authenticated_context(
            playwright, resolved_url, email=email
        )
        try:
            return check_context(context, resolved_url)
        finally:
            context.close()
            browser.close()


def register_command(app: typer.Typer) -> None:
    @app.command(name="smoke")
    def smoke(
        email: Annotated[
            str,
            typer.Option("--email", help="Email used for dev login."),
        ] = DEFAULT_EMAIL,
        base_url: Annotated[
            str | None,
            typer.Option(
                "--base-url",
                help="Target a running development app instead of the active Docker backend.",
            ),
        ] = None,
    ) -> None:
        """Check the main authenticated pages for HTTP and browser errors."""
        try:
            result = run_smoke(email=email, base_url=base_url)
        except (OSError, RuntimeError, ValueError, PlaywrightError) as error:
            err_console.print(f"[bold red]{error}[/bold red]")
            raise typer.Exit(1) from error

        for path in result.checked_paths:
            console.print(f"Checked {path}")
        if result.failures:
            for failure in result.failures:
                err_console.print(
                    f"[bold red]{failure.kind.upper()} {failure.path}:[/bold red] "
                    f"{failure.detail}"
                )
            raise typer.Exit(1)
        console.print(f"Smoke checks passed against {result.base_url}")
