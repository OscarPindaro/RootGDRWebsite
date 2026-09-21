"""Replay — `harness replay`.

Two kinds of recording:

* **ui** — what the user did in the browser (the app posts each step; see
  ``backend/replay/routes.py``). ``export`` writes a Playwright test.
* **backend** — the requests the app answered (a dev-only middleware appends
  them; see ``backend/replay/middleware.py``). ``start``/``stop`` switch it on
  and off, and ``export --mode backend`` writes an integration test.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Annotated, Literal

import httpx
import typer
import yaml
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
    client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"
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
    bundle_dir: Annotated[
        Path | None,
        typer.Option(
            "--bundle",
            help="Export the referenced worlds as content bundles into this "
            "directory, so the replay can run on another database.",
        ),
    ] = None,
    email: Annotated[
        str, typer.Option("--email", help="Dev login email for the bundle export.")
    ] = DEFAULT_EMAIL,
) -> None:
    """Generate a test from one recording."""
    try:
        if mode == "backend":
            plan = recordings.plan_backend(recordings.load_backend(session))
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
    if bundle_dir is not None and mode == "backend":
        _export_preconditions(plan, bundle_dir, base_url=None, email=email)


def _export_preconditions(
    plan: recordings.BackendPlan,
    directory: Path,
    base_url: str | None,
    email: str,
) -> None:
    """Export each referenced world as a content bundle (dev API)."""
    worlds = [item for item in plan.preconditions if "/worlds/" in item.path]
    if not worlds:
        console.print("No world preconditions to export.")
        return
    url = _dev_base_url(base_url)
    client = _client(url, email)
    try:
        for precondition in worlds:
            world_id = precondition.id
            response = client.get(f"/api/dev/worlds/{world_id}/export")
            if response.status_code != 200:
                err_console.print(
                    f"[yellow]Cannot export precondition {world_id}: "
                    f"{response.status_code}[/yellow]"
                )
                continue
            name = precondition.name or world_id
            destination = directory / f"{_slug(name)}.bundle.yaml"
            destination.write_text(
                yaml.safe_dump(response.json(), sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )
            console.print(f"[green]Bundle:[/green] {destination}")
    finally:
        client.close()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "world"


@replay_app.command()
def run(
    session: Annotated[str, typer.Argument(help="Recorded backend session id.")],
    base_url: Annotated[
        str | None, typer.Option("--base-url", help="App to replay against.")
    ] = None,
    email: Annotated[
        str, typer.Option("--email", help="Dev login email.")
    ] = DEFAULT_EMAIL,
    bundle: Annotated[
        list[Path] | None,
        typer.Option(
            "--bundle",
            help="Precondition bundle to import before replaying; repeat as needed.",
        ),
    ] = None,
) -> None:
    """Replay a backend recording against a running app, with rebound ids."""
    try:
        url = _dev_base_url(base_url)
        client = _client(url, email)
    except (RuntimeError, httpx.HTTPError) as error:
        err_console.print(f"[bold red]{error}[/bold red]")
        raise typer.Exit(1) from error

    try:
        plan = recordings.plan_backend(recordings.load_backend(session))
    except FileNotFoundError as error:
        err_console.print(f"[bold red]{error}[/bold red]")
        raise typer.Exit(1) from error

    _report_preconditions(plan)
    for path in bundle or []:
        _import_bundle(client, path)

    failures = 0
    bound: dict[str, str] = {}
    for index, request in enumerate(plan.requests, start=1):
        target = _bind_text(request.target, bound)
        body = _bind_value(request.body, bound)
        response = client.request(
            request.method, target, json=body if body is not None else None
        )
        mark = "ok" if response.status_code == request.expected_status else "FAIL"
        if mark == "FAIL":
            failures += 1
        console.print(
            f"{index:3d}. [{mark}] {request.method} {target} -> "
            f"{response.status_code} (expected {request.expected_status})",
            markup=False,
        )
        if (
            request.expected is not None
            and response.status_code == request.expected_status
        ):
            difference = _body_difference(response, request.expected)
            if difference:
                failures += 1
                console.print(f"     [content] {difference}", markup=False)
        if request.bind is not None and response.status_code == request.expected_status:
            identifier = _response_id(response)
            if identifier is None:
                err_console.print(
                    f"[bold red]Create response carries no id: {request.method} {target}[/bold red]"
                )
                failures += 1
            else:
                bound[request.bind] = identifier
    if failures:
        raise typer.Exit(1)


def _bind_value(value: object, bound: dict[str, str]) -> object:
    if isinstance(value, dict):
        return {key: _bind_value(item, bound) for key, item in value.items()}
    if isinstance(value, list):
        return [_bind_value(item, bound) for item in value]
    if isinstance(value, str):
        for variable, identifier in bound.items():
            value = value.replace("{" + variable + "}", identifier)
        return value
    return value


def _bind_target(target: str, bound: dict[str, str]) -> str:
    for variable, identifier in bound.items():
        target = target.replace("{" + variable + "}", identifier)
    return target


def _bind_text(target: str, bound: dict[str, str]) -> str:
    return _bind_target(target, bound)


def _is_json(response: httpx.Response) -> bool:
    return "application/json" in response.headers.get("content-type", "")


def _body_difference(response: httpx.Response, expected: object) -> str | None:
    """A short description of how the response body differs, or ``None``."""
    if not _is_json(response):
        return None
    actual = recordings.normalize_response(response.json())
    if actual == recordings.normalize_response(expected):
        return None
    return f"body differs: {json.dumps(actual)[:200]}"


def _response_id(response: httpx.Response) -> str | None:
    """Created id from a JSON response or an htmx/HTTP redirect header."""
    if _is_json(response):
        payload = response.json()
        if isinstance(payload, dict) and isinstance(payload.get("id"), str):
            return payload["id"]
    location = response.headers.get("hx-redirect") or response.headers.get(
        "location", ""
    )
    matches = recordings.UUID_VALUE.findall(location)
    return matches[-1] if matches else None


def _report_preconditions(plan: recordings.BackendPlan) -> None:
    if not plan.preconditions:
        return
    console.print("[yellow]Preconditions (objects the recording expects):[/yellow]")
    for item in plan.preconditions:
        label = f" ({item.name})" if item.name else ""
        console.print(f"  - {item.id} ({item.path})", markup=False)
    console.print(
        "Import the matching bundles with --bundle, or the steps that touch them fail."
    )


def _import_bundle(client: httpx.Client, path: Path) -> None:
    bundle = yaml.safe_load(path.read_text(encoding="utf-8"))
    response = client.post("/api/dev/worlds/import", json=bundle)
    if response.status_code != 200:
        err_console.print(
            f"[bold red]Bundle import failed ({response.status_code}): "
            f"{response.text[:200]}[/bold red]"
        )
        raise typer.Exit(1)
    result = response.json()
    console.print(f"[green]Imported[/green] {result['name']} ({result['id']})")


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
                "/api/replay/start",
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
            response = client.post("/api/replay/stop")
            response.raise_for_status()
        finally:
            client.close()
    except (RuntimeError, httpx.HTTPError) as error:
        err_console.print(f"[bold red]{error}[/bold red]")
        raise typer.Exit(1) from error
    console.print("[green]Recording stopped.[/green]")


def register_commands(app: typer.Typer) -> None:
    app.add_typer(replay_app, name="replay")
