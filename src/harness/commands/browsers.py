"""Browser runtime — `harness browsers`.

Installs the Playwright Chromium build the harness and the e2e tests use. It
goes to a repository-local directory (``.playwright-browsers``) rather than
Playwright's default ``~/.cache/ms-playwright``, which some environments prune
between runs — that is what made every browser run re-download it.
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Annotated

import typer
from rich.console import Console

from ..test.browser import BROWSERS_PATH

console = Console()
err_console = Console(stderr=True)


def register_commands(app: typer.Typer) -> None:
    @app.command(name="browsers")
    def browsers(
        force: Annotated[
            bool, typer.Option("--force", help="Reinstall even if already present.")
        ] = False,
    ) -> None:
        """Install Playwright Chromium into the repository."""
        if BROWSERS_PATH.exists() and not force:
            console.print(f"[green]Chromium already installed:[/green] {BROWSERS_PATH}")
            return

        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            env={**os.environ, "PLAYWRIGHT_BROWSERS_PATH": str(BROWSERS_PATH)},
        )
        if result.returncode != 0:
            err_console.print("[bold red]Could not install Chromium.[/bold red]")
            raise typer.Exit(1)
        console.print(f"[green]Chromium installed:[/green] {BROWSERS_PATH}")
