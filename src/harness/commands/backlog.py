"""Backlog CLI — `harness backlog ...`. Read/create only, never deletes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError
from rich.console import Console

from ..backlog.client import (
    BoardClient,
    BoardError,
    BoardTokenSource,
    default_token_source,
    record_table,
)

console = Console()
err_console = Console(stderr=True)
backlog_app = typer.Typer(
    no_args_is_help=True, help="Read and create tickets on the isolated board."
)


def _client(token_file: Path | None, base_url: str) -> BoardClient:
    source = (
        BoardTokenSource(token_file=token_file)
        if token_file is not None
        else default_token_source()
    )
    return BoardClient(base_url, source.token())


def _emit(
    payload: object, as_json: bool, rows: list[tuple[str, str]] | None = None
) -> None:
    if as_json:
        console.print_json(json.dumps(payload, default=str, ensure_ascii=False))
        return
    for identifier, title in rows or []:
        console.print(f"[bold]{identifier}[/bold]  {title}")


def _fail() -> None:
    err_console.print(
        "[bold red]Board operation failed; no change was confirmed.[/bold red]"
    )
    raise typer.Exit(1)


def register_commands(app: typer.Typer) -> None:
    @backlog_app.command("projects")
    def projects(
        token_file: Annotated[
            Path | None, typer.Option(help="Private token file.")
        ] = None,
        base_url: Annotated[
            str, typer.Option(help="Loopback tunnel base URL.")
        ] = "http://127.0.0.1:3458",
        query: Annotated[
            str | None, typer.Option("--query", help="Filter by title.")
        ] = None,
        as_json: Annotated[bool, typer.Option("--json")] = False,
    ) -> None:
        """List projects visible to the scoped token."""
        try:
            with _client(token_file, base_url) as client:
                records = client.projects(query)
            _emit(
                [record.model_dump(mode="json") for record in records],
                as_json,
                record_table(records),
            )
        except BoardError, ValidationError, OSError, ValueError:
            _fail()

    @backlog_app.command("list")
    def list_tasks(
        project: Annotated[int, typer.Option(help="Project id.")],
        token_file: Annotated[
            Path | None, typer.Option(help="Private token file.")
        ] = None,
        base_url: Annotated[
            str, typer.Option(help="Loopback tunnel base URL.")
        ] = "http://127.0.0.1:3458",
        query: Annotated[
            str | None, typer.Option("--query", help="Filter by title.")
        ] = None,
        as_json: Annotated[bool, typer.Option("--json")] = False,
    ) -> None:
        """List every task of one project, following pagination."""
        try:
            with _client(token_file, base_url) as client:
                records = client.tasks(project, query)
            _emit(
                [record.model_dump(mode="json") for record in records],
                as_json,
                record_table(records),
            )
        except BoardError, ValidationError, OSError, ValueError:
            _fail()

    @backlog_app.command("show")
    def show_task(
        task: Annotated[int, typer.Argument(help="Task id.")],
        token_file: Annotated[
            Path | None, typer.Option(help="Private token file.")
        ] = None,
        base_url: Annotated[
            str, typer.Option(help="Loopback tunnel base URL.")
        ] = "http://127.0.0.1:3458",
        as_json: Annotated[bool, typer.Option("--json")] = False,
    ) -> None:
        """Show one task with its comments."""
        try:
            with _client(token_file, base_url) as client:
                record = client.task(task)
                comments = client.comments(task)
            payload = {
                "task": record.model_dump(mode="json"),
                "comments": [item.model_dump(mode="json") for item in comments],
            }
            rows = [(str(record.id), record.title or "-")] + [
                (str(item.id), item.comment.splitlines()[0][:80]) for item in comments
            ]
            _emit(payload, as_json, rows)
        except BoardError, ValidationError, OSError, ValueError:
            _fail()

    @backlog_app.command("create")
    def create_task(
        project: Annotated[int, typer.Option(help="Project id.")],
        title: Annotated[str, typer.Option(help="Ticket title.")],
        token_file: Annotated[
            Path | None, typer.Option(help="Private token file.")
        ] = None,
        base_url: Annotated[
            str, typer.Option(help="Loopback tunnel base URL.")
        ] = "http://127.0.0.1:3458",
        description: Annotated[str, typer.Option(help="Ticket body.")] = "",
        bucket: Annotated[int | None, typer.Option(help="Explicit bucket id.")] = None,
        as_json: Annotated[bool, typer.Option("--json")] = False,
    ) -> None:
        """Create one ticket. An ambiguous timeout is never retried blindly."""
        try:
            with _client(token_file, base_url) as client:
                record = client.create_task(
                    project, title=title, description=description, bucket=bucket
                )
            _emit(record.model_dump(mode="json"), as_json, record_table([record]))
        except BoardError, ValidationError, OSError, ValueError:
            _fail()

    app.add_typer(backlog_app, name="backlog")
