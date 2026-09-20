"""Replay — `harness replay`.

Two kinds of recording:

* **ui** — what the user did in the browser (the app posts each step; see
  ``backend/replay/routes.py``). ``export`` writes a Playwright test.
* **backend** — the requests the app answered (a dev-only middleware appends
  them; see ``backend/replay/middleware.py``). ``start``/``stop`` switch it on
  and off, and ``export --mode backend`` writes an integration test.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

import httpx
import typer
from rich.console import Console

from .. import replay as recordings
from ..dev import state as dev_state
from ..test import state as test_state

console = Console()
err_console = Console(stderr=True)

replay_app = typer.Typer(
    no_args_is_help=True, help="Recorded sessions and the tests generated from them."
)

Mode = Literal["ui", "backend"]
DEFAULT_EMAIL = "e2e-admin@example.com"
MODE_OPTION = typer.Option("--mode", help="ui (browser steps) or backend (requests).")


def _dev_base_url(explicit: str | None) -> str:
    if explicit:
        return explicit.rstrip("/")
    dev = dev_state.read(test_state.worktree_root())
    if dev is None:
        raise RuntimeError(
            "No development stack. Run `harness dev up` first, or pass --base-url."
        )
    return f"http://127.0.0.1:{dev.work_port}"


def _client(base_url: str, email: str) -> httpx.Client:
    client = httpx.Client(base_url=base_url, timeout=10)
    response = client.post("/auth/dev-login", json={"email": email})
    response.raise_for_status()
    return client


@replay_app.command("list")
def list_sessions(
    mode: Annotated[str, MODE_OPTION] = "ui",
) -> None:
    """List the recorded sessions."""
    found = (
        recordings.backend_sessions() if mode == "backend" else recordings.sessions()
    )
    if not found:
        hint = (
            "`harness replay start`, work, then `harness replay stop`."
            if mode == "backend"
            else "Switch on 'Registra azioni' in the user menu, work, then list."
        )
        console.print(f"No {mode} recordings. {hint}")
        return
    for session in found:
        count = len(
            recordings.load_backend(session)
            if mode == "backend"
            else recordings.load(session)
        )
        console.print(f"{session}  ({count} steps)")


@replay_app.command()
def show(
    session: Annotated[str, typer.Argument(help="Recorded session id.")],
    mode: Annotated[str, MODE_OPTION] = "ui",
) -> None:
    """Print the steps of one recording."""
    try:
        if mode == "backend":
            for index, step in enumerate(recordings.load_backend(session), start=1):
                target = step.path + (f"?{step.query}" if step.query else "")
                console.print(
                    f"{index:3d}. {step.method:6s} {target} -> {step.status}",
                    markup=False,
                )
            return
        for index, step in enumerate(recordings.load(session), start=1):
            detail = step.selector or step.url or ""
            value = f" = {step.value!r}" if step.value else ""
            # markup=False: selectors contain square brackets, which rich would eat.
            console.print(f"{index:3d}. {step.kind:6s} {detail}{value}", markup=False)
    except FileNotFoundError as error:
        err_console.print(f"[bold red]{error}[/bold red]")
        raise typer.Exit(1) from error


@replay_app.command()
def diff(
    before: Annotated[str, typer.Argument(help="Earlier recorded session id.")],
    after: Annotated[str, typer.Argument(help="Later recorded session id.")],
    mode: Annotated[str, MODE_OPTION] = "ui",
) -> None:
    """Compare two recordings, ignoring volatile UUID and timestamp values."""
    try:
        if mode == "backend":
            result = recordings.render_diff(
                recordings.load_backend(before),
                recordings.load_backend(after),
                "backend",
            )
        else:
            result = recordings.render_diff(
                recordings.load(before), recordings.load(after), "ui"
            )
    except FileNotFoundError as error:
        err_console.print(f"[bold red]{error}[/bold red]")
        raise typer.Exit(1) from error
    console.print(result, markup=False)


@replay_app.command()
def export(
    session: Annotated[str, typer.Argument(help="Recorded session id.")],
    mode: Annotated[str, MODE_OPTION] = "ui",
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Where to write the test."),
    ] = None,
) -> None:
    """Generate a test from one recording."""
    try:
        if mode == "backend":
            source = recordings.render_backend_test(
                session, recordings.load_backend(session)
            )
            destination = (
                output or Path("tests/integration") / f"test_replay_{session}.py"
            )
        else:
            source = recordings.render_test(session, recordings.load(session))
            destination = output or Path("tests/e2e") / f"test_replay_{session}.py"
    except FileNotFoundError as error:
        err_console.print(f"[bold red]{error}[/bold red]")
        raise typer.Exit(1) from error

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(source, encoding="utf-8")
    console.print(f"[green]Test written:[/green] {destination}")
    console.print(
        f"Run it with `uv run harness test {mode if mode == 'ui' else 'integration'}`."
    )


@replay_app.command()
def start(
    base_url: Annotated[
        str | None, typer.Option("--base-url", help="App to record against.")
    ] = None,
    email: Annotated[
        str, typer.Option("--email", help="Dev login email.")
    ] = DEFAULT_EMAIL,
    read_only: Annotated[
        bool,
        typer.Option("--read-only", help="Record GET, HEAD, and OPTIONS only."),
    ] = False,
    exclude: Annotated[
        list[str] | None,
        typer.Option("--exclude", help="Path prefix to omit; repeat as needed."),
    ] = None,
) -> None:
    """Start recording backend calls."""
    try:
        url = _dev_base_url(base_url)
        client = _client(url, email)
        try:
            response = client.post(
                "/api/dev/replay/start",
                json={"read_only": read_only, "exclude": exclude or []},
            )
            response.raise_for_status()
            session = response.json()["session"]
        finally:
            client.close()
    except (RuntimeError, httpx.HTTPError) as error:
        err_console.print(f"[bold red]{error}[/bold red]")
        raise typer.Exit(1) from error
    console.print(f"[green]Recording backend calls as[/green] {session}")
    console.print(
        f"Work, then `harness replay stop` and "
        f"`harness replay export {session} --mode backend`."
    )


@replay_app.command()
def stop(
    base_url: Annotated[
        str | None, typer.Option("--base-url", help="App that is recording.")
    ] = None,
    email: Annotated[
        str, typer.Option("--email", help="Dev login email.")
    ] = DEFAULT_EMAIL,
) -> None:
    """Stop recording backend calls."""
    try:
        url = _dev_base_url(base_url)
        client = _client(url, email)
        try:
            response = client.post("/api/dev/replay/stop")
            response.raise_for_status()
        finally:
            client.close()
    except (RuntimeError, httpx.HTTPError) as error:
        err_console.print(f"[bold red]{error}[/bold red]")
        raise typer.Exit(1) from error
    console.print("[green]Recording stopped.[/green]")


def register_commands(app: typer.Typer) -> None:
    app.add_typer(replay_app, name="replay")
