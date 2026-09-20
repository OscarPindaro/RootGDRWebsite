"""Replay — `harness replay`.

Lists the sessions recorded in the browser, prints one, and generates a
Playwright test from it. Recording itself happens in the app: switch on
"Registra azioni" in the user menu, work normally, then export.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from .. import replay as recordings

console = Console()
err_console = Console(stderr=True)

replay_app = typer.Typer(
    no_args_is_help=True, help="Recorded sessions and the tests generated from them."
)


@replay_app.command("list")
def list_sessions() -> None:
    """List the recorded sessions."""
    found = recordings.sessions()
    if not found:
        console.print(
            "No recordings. Switch on 'Registra azioni' in the user menu, work, "
            "then run `harness replay list`."
        )
        return
    for session in found:
        steps = recordings.load(session)
        console.print(f"{session}  ({len(steps)} steps)")


@replay_app.command()
def show(session: Annotated[str, typer.Argument(help="Recorded session id.")]) -> None:
    """Print the steps of one recording."""
    try:
        steps = recordings.load(session)
    except FileNotFoundError as error:
        err_console.print(f"[bold red]{error}[/bold red]")
        raise typer.Exit(1) from error
    for index, step in enumerate(steps, start=1):
        detail = step.selector or step.url or ""
        value = f" = {step.value!r}" if step.value else ""
        # markup=False: selectors contain square brackets, which rich would eat.
        console.print(f"{index:3d}. {step.kind:6s} {detail}{value}", markup=False)


@replay_app.command()
def export(
    session: Annotated[str, typer.Argument(help="Recorded session id.")],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Where to write the test."),
    ] = None,
) -> None:
    """Generate a Playwright test from one recording."""
    try:
        steps = recordings.load(session)
    except FileNotFoundError as error:
        err_console.print(f"[bold red]{error}[/bold red]")
        raise typer.Exit(1) from error

    destination = output or Path("tests/e2e") / f"test_replay_{session}.py"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(recordings.render_test(session, steps), encoding="utf-8")
    console.print(f"[green]Test written:[/green] {destination}")
    console.print(f"Run it with `uv run harness test e2e {destination}`.")


def register_commands(app: typer.Typer) -> None:
    app.add_typer(replay_app, name="replay")
