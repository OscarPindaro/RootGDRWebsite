"""Artifact management — `harness artifacts ...`.

Every artifact-producing command records its files under
``harness-artifacts/<run-id>/`` with a manifest. These commands list, inspect
and clean up those runs. Cleanup is destructive, so it is a dry run by
default and requires ``--apply``.
"""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Annotated

import typer
from rich.console import Console

from .. import artifacts

artifacts_app = typer.Typer(no_args_is_help=True, help="Manage artifact runs.")
console = Console()
err_console = Console(stderr=True)


def _duration(value: str) -> timedelta:
    match = re.fullmatch(r"(\d+)([mhd])", value)
    if not match:
        raise typer.BadParameter("Use a duration like 30m, 12h or 7d")
    return timedelta(
        seconds=int(match.group(1)) * {"m": 60, "h": 3600, "d": 86400}[match.group(2)]
    )


def _human(size: int) -> str:
    for unit in ("B", "KiB", "MiB", "GiB"):
        if size < 1024:
            return f"{size:.0f}{unit}" if unit != "B" else f"{size}B"
        size /= 1024
    return f"{size}TB"


@artifacts_app.command("list")
def list_command(
    kind: Annotated[
        str | None, typer.Option("--kind", help="Only runs of this kind.")
    ] = None,
) -> None:
    """List artifact runs, newest first."""
    runs = artifacts.list_runs(kind=kind)
    if not runs:
        console.print("No artifact runs.")
        return
    for manifest in runs:
        console.print(
            f"{manifest.id}  {manifest.kind:12} {manifest.status.value:11} "
            f"{manifest.command}"
        )


@artifacts_app.command("show")
def show_command(
    run_id: Annotated[str, typer.Argument(help="Run id, as shown by `list`.")],
) -> None:
    """Show one run's manifest and its files."""
    try:
        run = artifacts.load(run_id)
    except artifacts.ArtifactError as error:
        err_console.print(f"[bold red]{error}[/bold red]")
        raise typer.Exit(1) from error
    manifest = run.manifest
    console.print(f"{manifest.id} ({manifest.kind}, {manifest.status.value})")
    console.print(f"  command: {manifest.command or '-'}")
    console.print(f"  started: {manifest.started_at.isoformat()}")
    if manifest.revision:
        console.print(f"  revision: {manifest.revision}")
    for file in manifest.files:
        console.print(f"  [{file.kind.value}] {file.path}")


@artifacts_app.command("clean")
def clean_command(
    older_than: Annotated[
        str | None,
        typer.Option("--older-than", help="Only runs older than this (30m, 12h, 7d)."),
    ] = None,
    keep_latest: Annotated[
        int | None, typer.Option("--keep-latest", help="Keep the N newest runs.")
    ] = None,
    kind: Annotated[
        str | None, typer.Option("--kind", help="Only runs of this kind.")
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", help="Also delete the most recent failed run."),
    ] = False,
    apply: Annotated[
        bool, typer.Option("--apply", help="Delete for real (default: dry run).")
    ] = False,
) -> None:
    """Delete artifact runs, dry-run unless --apply."""
    if older_than is None and keep_latest is None:
        raise typer.BadParameter("Give --older-than and/or --keep-latest.")
    try:
        plan = artifacts.cleanup(
            older_than=_duration(older_than) if older_than else None,
            keep_latest=keep_latest,
            kind=kind,
            force=force,
            dry_run=not apply,
        )
    except artifacts.ArtifactError as error:
        err_console.print(f"[bold red]{error}[/bold red]")
        raise typer.Exit(1) from error
    for directory in plan.directories:
        console.print(directory)
    console.print(
        f"{len(plan.directories)} run(s), {_human(plan.bytes)} "
        f"{'deleted' if plan.deleted else 'would be deleted'}"
    )
    if not apply and plan.directories:
        console.print("Dry run: pass --apply to delete.")


def register_command(app: typer.Typer) -> None:
    app.add_typer(artifacts_app, name="artifacts")
