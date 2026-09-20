"""Development stack — `harness dev`.

One Postgres container with two databases and one app container per database:
``app-work`` (scratch, the agent's) on ``--work-port`` and ``app-show``
(showcase, what the user is shown) on ``--show-port``. ``reset --db show`` drops
and re-migrates the showcase database and seeds the reference world into it, so
what is shown is never scratch data. The test environment is a separate stack
with its own database.
"""

from __future__ import annotations

import json
import os
import subprocess
import urllib.request
from typing import Annotated

import typer
from dotenv import dotenv_values
from rich.console import Console

from ..dev import compose, state
from ..test import state as test_state

console = Console()
err_console = Console(stderr=True)

dev_app = typer.Typer(
    no_args_is_help=True, help="Development stack (scratch + showcase)."
)

DEFAULT_EMAIL = "e2e-admin@example.com"
DB_OPTION = typer.Option("--db", help="Which database: work or show.")
EMAIL_OPTION = typer.Option("--email", help="Owner used to seed the reference world.")


def _require() -> state.DevState:
    dev = state.read(test_state.worktree_root())
    if dev is None:
        err_console.print(
            "[bold red]No development stack. Run `harness dev up` first.[/bold red]"
        )
        raise typer.Exit(1)
    return dev


def _database(name: str) -> str:
    if name not in {"work", "show"}:
        raise typer.BadParameter("--db must be 'work' or 'show'")
    values = dotenv_values(compose.ENV_FILE)
    key = "POSTGRES_DB" if name == "work" else "DEV_SHOW_DB"
    return values.get(key) or ("root_gdr_dev" if name == "work" else "root_gdr_show")


def _database_environment(dev: state.DevState, database: str) -> dict[str, str]:
    """Point the app's own config at one dev database, from the host."""
    return {
        **os.environ,
        "ENV_FILE": str(compose.ENV_FILE),
        "YAML_CONFIG_FILE": "config.yaml",
        "DATABASE__HOST": "127.0.0.1",
        "DATABASE__PORT": str(dev.db_port),
        "DATABASE__DB": database,
        "MIGRATOR__HOST": "127.0.0.1",
        "MIGRATOR__PORT": str(dev.db_port),
        "MIGRATOR__DB": database,
    }


def _run(environment: dict[str, str], args: list[str]) -> None:
    result = subprocess.run(
        ["uv", "run", *args], cwd=compose._REPO_ROOT, env=environment
    )
    if result.returncode != 0:
        raise RuntimeError(f"{' '.join(args)} failed")


def _ensure_user(port: int, email: str) -> None:
    """Sign in through the dev login, which creates the bootstrap admin."""
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/auth/dev-login",
        data=json.dumps({"email": email}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10):
        pass


def _prepare(dev: state.DevState, database: str, email: str, port: int) -> None:
    environment = _database_environment(dev, database)
    _run(environment, ["alembic", "upgrade", "head"])
    _ensure_user(port, email)
    _run(environment, ["harness", "content", "seed", "--email", email])


@dev_app.command()
def up(
    reload: Annotated[
        bool, typer.Option("--reload/--no-reload", help="Reload the apps on change.")
    ] = True,
    build: Annotated[
        bool, typer.Option("--build/--no-build", help="Build the app image.")
    ] = True,
    work_port: Annotated[int, typer.Option("--work-port", min=1, max=65535)] = (
        state.DEFAULT_WORK_PORT
    ),
    show_port: Annotated[int, typer.Option("--show-port", min=1, max=65535)] = (
        state.DEFAULT_SHOW_PORT
    ),
    db_port: Annotated[int, typer.Option("--db-port", min=1, max=65535)] = (
        state.DEFAULT_DB_PORT
    ),
) -> None:
    """Start the development stack."""
    root = test_state.worktree_root()
    dev = state.read(root)
    if dev is None:
        dev = state.DevState(
            worktree=root,
            compose_project=state.project_name(root),
            work_port=work_port,
            show_port=show_port,
            db_port=db_port,
        )
        state.write(dev, root)
    try:
        compose.up(dev, reload=reload, build=build)
    except compose.ComposeError as error:
        err_console.print(f"[bold red]{error}[/bold red]")
        raise typer.Exit(1) from error
    console.print(f"[green]Work (scratch):[/green]   http://localhost:{dev.work_port}")
    console.print(f"[green]Showcase:[/green]        http://localhost:{dev.show_port}")
    console.print(f"Database:        localhost:{dev.db_port}")
    console.print(f"Reload:          {'on' if reload else 'off'}")


@dev_app.command()
def down() -> None:
    """Stop the development stack and delete its data."""
    root = test_state.worktree_root()
    dev = state.read(root)
    if dev is None:
        console.print("No development stack for this worktree.")
        return
    try:
        compose.down(dev)
    except compose.ComposeError as error:
        err_console.print(f"[bold red]{error}[/bold red]")
        raise typer.Exit(1) from error
    state.clear(root)
    console.print("[green]Development stack stopped.[/green]")


@dev_app.command()
def status() -> None:
    """Show the development stack."""
    dev = _require()
    console.print(
        f"project={dev.compose_project} work={dev.work_port} "
        f"show={dev.show_port} db={dev.db_port}"
    )
    try:
        console.print(compose.status_text(dev))
    except compose.ComposeError as error:
        err_console.print(f"[bold red]{error}[/bold red]")
        raise typer.Exit(1) from error


@dev_app.command()
def seed(
    db: Annotated[str, DB_OPTION] = "work",
    email: Annotated[str, EMAIL_OPTION] = DEFAULT_EMAIL,
) -> None:
    """Migrate and import the reference world into one database."""
    dev = _require()
    database = _database(db)
    port = dev.work_port if db == "work" else dev.show_port
    try:
        _prepare(dev, database, email, port)
    except (RuntimeError, OSError) as error:
        err_console.print(f"[bold red]{error}[/bold red]")
        raise typer.Exit(1) from error
    console.print(f"[green]Seeded {db} ({database}).[/green]")


@dev_app.command()
def reset(
    db: Annotated[str, DB_OPTION] = "show",
    email: Annotated[str, EMAIL_OPTION] = DEFAULT_EMAIL,
) -> None:
    """Drop and recreate one database, then seed the reference world."""
    dev = _require()
    database = _database(db)
    port = dev.work_port if db == "work" else dev.show_port
    values = dotenv_values(compose.ENV_FILE)
    migrator = values.get("MIGRATOR__USER", "migrator_user")
    app_user = values.get("DATABASE__USER", "app_user")
    sql = (
        "DROP SCHEMA public CASCADE; CREATE SCHEMA public; "
        f"ALTER SCHEMA public OWNER TO {migrator}; "
        f"GRANT USAGE, CREATE ON SCHEMA public TO {migrator}; "
        f"GRANT USAGE ON SCHEMA public TO {app_user}; "
        f"ALTER DEFAULT PRIVILEGES FOR ROLE {migrator} IN SCHEMA public "
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {app_user}; "
        f"ALTER DEFAULT PRIVILEGES FOR ROLE {migrator} IN SCHEMA public "
        f"GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO {app_user};"
    )
    try:
        compose.psql(dev, database, sql)
        _prepare(dev, database, email, port)
    except (compose.ComposeError, RuntimeError, OSError) as error:
        err_console.print(f"[bold red]{error}[/bold red]")
        raise typer.Exit(1) from error
    console.print(f"[green]{db} database ({database}) recreated and seeded.[/green]")


def register_commands(app: typer.Typer) -> None:
    app.add_typer(dev_app, name="dev")
