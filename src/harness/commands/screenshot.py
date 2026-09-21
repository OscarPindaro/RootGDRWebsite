from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from .. import artifacts
from ..test import state
from ..test.browser import capture_screenshots

console = Console()
err_console = Console(stderr=True)


def register_command(app: typer.Typer) -> None:
    @app.command(name="screenshot")
    def screenshot(
        path: Annotated[str, typer.Argument(help="Application path to render.")],
        email: Annotated[
            str,
            typer.Option("--email", help="Email used for dev login."),
        ],
        name: Annotated[
            str | None,
            typer.Option("--name", help="Filename prefix for both screenshots."),
        ] = None,
        output_dir: Annotated[
            Path | None,
            typer.Option(
                "--output-dir",
                help="Directory for the PNG files (default: a new artifact run).",
            ),
        ] = None,
        click: Annotated[
            str | None,
            typer.Option(
                "--click", help="Click the first matching locator before capture."
            ),
        ] = None,
        hover: Annotated[
            str | None,
            typer.Option(
                "--hover", help="Hover the first matching locator before capture."
            ),
        ] = None,
        expect_visible: Annotated[
            str | None,
            typer.Option(
                "--expect-visible",
                help="Require the first matching locator to be visible before capture.",
            ),
        ] = None,
        expected_status: Annotated[
            int,
            typer.Option(
                "--expect-status",
                min=100,
                max=599,
                help="Required HTTP status for the page navigation.",
            ),
        ] = 200,
        base_url: Annotated[
            str | None,
            typer.Option(
                "--base-url",
                help="Target a running app (e.g. the dev showcase) instead of the "
                "active harness environment.",
            ),
        ] = None,
    ) -> None:
        """Capture authenticated desktop and phone screenshots."""
        run = None
        if output_dir is None:
            run = artifacts.create_run("screenshot", command=f"screenshot {path}")
            destination = run.directory / artifacts.ArtifactKind.SCREENSHOTS.value
            output_dir = destination.relative_to(state.worktree_root())
        try:
            result = capture_screenshots(
                path,
                email=email,
                name=name,
                output_dir=output_dir,
                click=click,
                hover=hover,
                expect_visible=expect_visible,
                expected_status=expected_status,
                base_url=base_url,
            )
        except (OSError, RuntimeError, ValueError) as error:
            if run is not None:
                run.mark_failed()
            err_console.print(f"[bold red]{error}[/bold red]")
            raise typer.Exit(1) from error
        if run is not None:
            run.register(artifacts.ArtifactKind.SCREENSHOTS, result.desktop)
            run.register(artifacts.ArtifactKind.SCREENSHOTS, result.phone)
            run.mark_passed()
            console.print(f"Run: {run.id}")
        console.print(f"Desktop: {result.desktop}")
        console.print(f"Phone: {result.phone}")
        for error in result.console_errors:
            err_console.print(f"Browser console: {error}")
