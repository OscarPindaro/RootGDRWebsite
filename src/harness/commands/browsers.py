"""Browser runtime — `harness browsers`.

Installs the Playwright Chromium build the harness and the tests use, into the
repository-local directory (``.playwright-browsers``) unless an explicit
``PLAYWRIGHT_BROWSERS_PATH`` says otherwise. Playwright's default cache
(``~/.cache/ms-playwright``) is pruned by some environments, which made every
browser run re-download it. The command verifies the required revision and its
binary, and distinguishes missing OS libraries from a missing browser.
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Annotated

import typer
from rich.console import Console

from ..browser_runtime import ensure_browsers_path, missing_browsers

console = Console()
err_console = Console(stderr=True)

_OS_LIBRARY_MARKERS = (
    "missing dependencies",
    "shared libraries",
    "libnss",
    "libatk",
    "libgbm",
)


def _launch_problem() -> str | None:
    """None when Chromium starts, otherwise a bounded problem class."""
    from playwright.sync_api import Error as PlaywrightError  # noqa: PLC0415
    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            browser.close()
    except PlaywrightError as error:
        text = str(error).lower()
        if any(marker in text for marker in _OS_LIBRARY_MARKERS):
            return "os-libraries"
        return "launch"
    return None


def _report_launch_problem(problem: str) -> None:
    if problem == "os-libraries":
        err_console.print(
            "[bold red]Chromium is installed but the OS libraries it needs "
            "are missing.[/bold red] On a CI runner install them with "
            "`uv run harness browsers --with-deps`; on Fedora install them "
            "manually."
        )
    else:
        err_console.print(
            "[bold red]Chromium is installed but does not start; "
            "run `uv run harness browsers --force`.[/bold red]"
        )


def register_commands(app: typer.Typer) -> None:
    @app.command(name="browsers")
    def browsers(
        force: Annotated[
            bool, typer.Option("--force", help="Reinstall even if already present.")
        ] = False,
        with_deps: Annotated[
            bool,
            typer.Option(
                "--with-deps",
                help="Also install OS packages (CI runners; needs privileges).",
            ),
        ] = False,
    ) -> None:
        """Install Playwright Chromium into the repository."""
        target = ensure_browsers_path()
        if not force and not missing_browsers(target):
            problem = _launch_problem()
            if problem is not None:
                _report_launch_problem(problem)
                raise typer.Exit(1)
            console.print(f"[green]Chromium is installed:[/green] {target}")
            return

        command = [sys.executable, "-m", "playwright", "install", "chromium"]
        if with_deps:
            command.append("--with-deps")
        result = subprocess.run(
            command,
            env={**os.environ, "PLAYWRIGHT_BROWSERS_PATH": str(target)},
        )
        if result.returncode != 0:
            err_console.print("[bold red]Could not install Chromium.[/bold red]")
            raise typer.Exit(1)
        missing = missing_browsers(target)
        if missing:
            err_console.print(
                f"[bold red]Chromium installation is incomplete: "
                f"{', '.join(missing)}[/bold red]"
            )
            raise typer.Exit(1)
        problem = _launch_problem()
        if problem is not None:
            _report_launch_problem(problem)
            raise typer.Exit(1)
        console.print(f"[green]Chromium installed:[/green] {target}")
