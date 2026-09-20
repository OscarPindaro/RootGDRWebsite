"""Prototype harness — `harness prototype serve`.

Serves the static prototype in `prototypes/devin-prototype/` so the visual
reference can be opened next to the real application.
"""

from __future__ import annotations

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

console = Console()
err_console = Console(stderr=True)

prototype_app = typer.Typer(no_args_is_help=True, help="Serve the static prototype.")

DEFAULT_DIRECTORY = Path("prototypes/devin-prototype")
DEFAULT_PORT = 4174


@prototype_app.command()
def serve(
    port: Annotated[int, typer.Option("--port", "-p", min=1, max=65535)] = DEFAULT_PORT,
    directory: Annotated[
        Path,
        typer.Option("--directory", "-d", help="Prototype directory to serve."),
    ] = DEFAULT_DIRECTORY,
    host: Annotated[str, typer.Option("--host")] = "127.0.0.1",
) -> None:
    """Serve the prototype over HTTP (Ctrl+C to stop)."""
    if not directory.is_dir():
        err_console.print(
            f"[bold red]{directory}: prototype directory not found[/bold red]"
        )
        raise typer.Exit(1)

    handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
    with ThreadingHTTPServer((host, port), handler) as server:
        console.print(f"[green]Prototype:[/green] http://{host}:{port}/index.html")
        console.print("Press Ctrl+C to stop.")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            console.print("\n[yellow]Stopped.[/yellow]")


def register_commands(app: typer.Typer) -> None:
    app.add_typer(prototype_app, name="prototype")
