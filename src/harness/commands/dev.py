"""Developer loop — `harness dev`.

Starts the docker environment with the backend reloading on every change and
imports the reference world, so edit → refresh is the whole iteration. Reload is
on by default; ``--no-reload`` restores the fixed-backend behaviour.
"""

from __future__ import annotations

import os
import subprocess
from typing import Annotated

import typer
from rich.console import Console

from ..test import environment, state

console = Console()
err_console = Console(stderr=True)

DEFAULT_EMAIL = "e2e-admin@example.com"


def _seed(environment_state: state.EnvironmentState, email: str) -> None:
    """Import the reference world against the active environment's database.

    A subprocess, because ``backend.config`` reads ``ENV_FILE`` /
    ``YAML_CONFIG_FILE`` when it is imported and the CLI imports it before this
    command runs — the same reason the documented direct invocation passes them.
    """
    process = subprocess.run(
        ["uv", "run", "harness", "content", "seed", "--email", email],
        cwd=state.worktree_root(),
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "ENV_FILE": str(environment_state.config.env),
            "YAML_CONFIG_FILE": str(environment_state.config.local),
        },
    )
    if process.returncode != 0:
        raise RuntimeError(
            process.stderr.strip() or "could not seed the reference world"
        )
    # The seed CLI logs every SQL statement; only its final summary is useful.
    summary = [line for line in process.stdout.splitlines() if line.strip()]
    if summary:
        console.print(summary[-1])


def register_commands(app: typer.Typer) -> None:
    @app.command(name="dev")
    def dev(
        reload: Annotated[
            bool,
            typer.Option("--reload/--no-reload", help="Reload the backend on change."),
        ] = True,
        seed: Annotated[
            bool,
            typer.Option("--seed/--no-seed", help="Import the reference world."),
        ] = True,
        email: Annotated[
            str,
            typer.Option("--email", help="Owner used to seed the reference world."),
        ] = DEFAULT_EMAIL,
    ) -> None:
        """Start the development environment and seed the reference world."""
        try:
            environment_state = environment.up(
                state.EnvironmentMode.DOCKER, reload=reload
            )
        except environment.EnvironmentError as error:
            err_console.print(f"[bold red]{error}[/bold red]")
            raise typer.Exit(1) from error

        if seed:
            try:
                _seed(environment_state, email)
            except RuntimeError as error:
                err_console.print(f"[bold red]{error}[/bold red]")
                raise typer.Exit(1) from error

        console.print(
            f"[green]Development backend:[/green] "
            f"http://localhost:{environment_state.ports.backend}"
        )
        console.print(f"Reload: {'on' if reload else 'off'}")
