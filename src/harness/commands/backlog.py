"""Backlog CLI — `harness backlog ...`. Read/create only, never deletes."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError
from rich.console import Console

from ..backlog.client import (
    BoardClient,
    BoardError,
    BoardTask,
    BoardTokenSource,
    BoardView,
    default_token_source,
    record_table,
)
from ..backlog.plan import PLAN, load_plan_tickets, ticket_description
from ..backlog.requests import REPO_ROOT, REQUESTS_DIR, scan_requests

console = Console()
err_console = Console(stderr=True)
backlog_app = typer.Typer(
    no_args_is_help=True, help="Read and create tickets on the isolated board."
)

WORKFLOW_BUCKETS = ("Backlog", "In corso", "Review", "Conclusi")
# What a new kanban view starts with; the workflow reuses and renames them.
NEW_VIEW_BUCKETS = {"Backlog": "To-Do", "In corso": "Doing", "Conclusi": "Done"}
TICKET_KEY = re.compile(r"^REQ-\d{4}/T\d{2}(?!\d)")


def _kanban_view(client: BoardClient, project: int, view: int | None) -> BoardView:
    if view is not None:
        board_view = client.view(project, view)
        if board_view.view_kind != "kanban":
            raise BoardError("The configured view is not a kanban view")
        return board_view
    kanban = [item for item in client.views(project) if item.view_kind == "kanban"]
    if not kanban:
        raise BoardError("Project has no kanban view to configure")
    return next((item for item in kanban if item.title == "Kanban"), kanban[0])


def _board_keys(tasks: list[BoardTask]) -> dict[str, int]:
    keys: dict[str, int] = {}
    for task in tasks:
        found = TICKET_KEY.match(task.title)
        if found:
            key = found.group(0)
            keys[key] = keys.get(key, 0) + 1
    return keys


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

    @backlog_app.command("check-requests")
    def check_requests(
        root: Annotated[Path, typer.Option(help="Repository root.")] = REPO_ROOT,
    ) -> None:
        """Validate request frontmatter, links and references (offline)."""
        try:
            documents, issues = scan_requests(root)
        except OSError:
            _fail()
            return
        for issue in issues:
            err_console.print(f"[bold red]{issue.path}: {issue.detail}[/bold red]")
        if not documents:
            err_console.print(
                f"[bold red]No request document found under "
                f"{root / REQUESTS_DIR}[/bold red]"
            )
            raise typer.Exit(1)
        if issues:
            raise typer.Exit(1)
        console.print(f"[green]{len(documents)} request document(s) valid.[/green]")

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

    @backlog_app.command("move")
    def move_task(
        task: Annotated[int, typer.Argument(help="Task id.")],
        project: Annotated[int, typer.Option(help="Project id.")],
        view: Annotated[int, typer.Option(help="Kanban view id.")],
        bucket: Annotated[int, typer.Option(help="Target bucket id.")],
        token_file: Annotated[
            Path | None, typer.Option(help="Private token file.")
        ] = None,
        base_url: Annotated[
            str, typer.Option(help="Loopback tunnel base URL.")
        ] = "http://127.0.0.1:3458",
        as_json: Annotated[bool, typer.Option("--json")] = False,
    ) -> None:
        """Place a task in one bucket. The current placement is read first, so
        a retry after an ambiguous timeout never writes twice."""
        try:
            with _client(token_file, base_url) as client:
                current = client.task_bucket(project, view, task)
                changed = current != bucket
                if changed:
                    client.place_task(project, view, bucket, task)
            detail = "moved" if changed else "already there"
            _emit(
                {"task": task, "bucket": bucket, "changed": changed},
                as_json,
                [(str(task), f"bucket {bucket} ({detail})")],
            )
        except BoardError, ValidationError, OSError, ValueError:
            _fail()

    @backlog_app.command("close")
    def close_task(
        task: Annotated[int, typer.Argument(help="Task id.")],
        project: Annotated[int, typer.Option(help="Project id.")],
        view: Annotated[int, typer.Option(help="Kanban view id.")],
        token_file: Annotated[
            Path | None, typer.Option(help="Private token file.")
        ] = None,
        base_url: Annotated[
            str, typer.Option(help="Loopback tunnel base URL.")
        ] = "http://127.0.0.1:3458",
        as_json: Annotated[bool, typer.Option("--json")] = False,
    ) -> None:
        """Close a task into the view's done bucket; without one, only the
        done flag changes. The current placement is read first."""
        try:
            with _client(token_file, base_url) as client:
                board_view = client.view(project, view)
                if board_view.done_bucket_id > 0:
                    current = client.task_bucket(project, view, task)
                    changed = current != board_view.done_bucket_id
                    if changed:
                        client.place_task(
                            project, view, board_view.done_bucket_id, task
                        )
                    bucket = board_view.done_bucket_id
                    detail = "closed" if changed else "already in the done bucket"
                else:
                    record = client.task(task)
                    changed = not record.done
                    if changed:
                        client.set_task_done(task, True)
                    bucket = 0
                    detail = "closed (done flag)" if changed else "already closed"
            _emit(
                {"task": task, "bucket": bucket, "done": True, "changed": changed},
                as_json,
                [(str(task), detail)],
            )
        except BoardError, ValidationError, OSError, ValueError:
            _fail()

    @backlog_app.command("reopen")
    def reopen_task(
        task: Annotated[int, typer.Argument(help="Task id.")],
        project: Annotated[int, typer.Option(help="Project id.")],
        view: Annotated[int, typer.Option(help="Kanban view id.")],
        bucket: Annotated[
            int | None, typer.Option(help="Bucket id; defaults to the view's.")
        ] = None,
        token_file: Annotated[
            Path | None, typer.Option(help="Private token file.")
        ] = None,
        base_url: Annotated[
            str, typer.Option(help="Loopback tunnel base URL.")
        ] = "http://127.0.0.1:3458",
        as_json: Annotated[bool, typer.Option("--json")] = False,
    ) -> None:
        """Reopen a closed task into a non-done bucket; without a done bucket,
        only the done flag changes."""
        try:
            with _client(token_file, base_url) as client:
                board_view = client.view(project, view)
                target = bucket if bucket is not None else board_view.default_bucket_id
                if board_view.done_bucket_id > 0:
                    if target <= 0 or target == board_view.done_bucket_id:
                        err_console.print(
                            "[bold red]Reopen needs a non-done bucket: pass "
                            "--bucket or configure the view's default bucket."
                            "[/bold red]"
                        )
                        raise typer.Exit(1)
                    record = client.task(task)
                    current = client.task_bucket(project, view, task)
                    changed = current != target or record.done
                    if changed:
                        client.place_task(project, view, target, task)
                    detail = "reopened" if changed else "already open"
                    payload = {"task": task, "bucket": target, "done": False}
                else:
                    record = client.task(task)
                    changed = record.done
                    if changed:
                        client.set_task_done(task, False)
                    detail = "reopened (done flag)" if changed else "already open"
                    payload = {"task": task, "bucket": 0, "done": False}
            _emit(payload, as_json, [(str(task), detail)])
        except BoardError, ValidationError, OSError, ValueError:
            _fail()

    @backlog_app.command("comment")
    def comment_task(
        task: Annotated[int, typer.Argument(help="Task id.")],
        text: Annotated[str, typer.Option(help="Comment body.")],
        marker: Annotated[
            str | None,
            typer.Option(help="Idempotency marker, e.g. the ticket id."),
        ] = None,
        token_file: Annotated[
            Path | None, typer.Option(help="Private token file.")
        ] = None,
        base_url: Annotated[
            str, typer.Option(help="Loopback tunnel base URL.")
        ] = "http://127.0.0.1:3458",
        as_json: Annotated[bool, typer.Option("--json")] = False,
    ) -> None:
        """Comment on a task. With --marker the write is idempotent and an
        ambiguous timeout re-reads before concluding anything."""
        try:
            with _client(token_file, base_url) as client:
                if marker is None:
                    record = client.add_comment(task, text)
                    created = True
                else:
                    record, created = client.add_comment_once(task, text, marker)
            detail = "created" if created else "already present"
            _emit(
                {"task": task, "comment_id": record.id, "created": created},
                as_json,
                [(str(record.id), detail)],
            )
        except BoardError, ValidationError, OSError, ValueError:
            _fail()

    @backlog_app.command("workflow")
    def workflow(
        project: Annotated[int, typer.Option(help="Project id.")],
        view: Annotated[
            int | None,
            typer.Option(help="Kanban view id; defaults to the project's."),
        ] = None,
        token_file: Annotated[
            Path | None, typer.Option(help="Private token file.")
        ] = None,
        base_url: Annotated[
            str, typer.Option(help="Loopback tunnel base URL.")
        ] = "http://127.0.0.1:3458",
        as_json: Annotated[bool, typer.Option("--json")] = False,
    ) -> None:
        """Ensure the kanban workflow — Backlog, In corso, Review, Conclusi —
        with explicit default and done buckets. Needs a token allowed to
        create views and buckets, so normally the owner's, not the tooling
        token."""
        try:
            with _client(token_file, base_url) as client:
                board_view = _kanban_view(client, project, view)
                buckets = {
                    item.title: item for item in client.buckets(project, board_view.id)
                }
                renamed: list[str] = []
                created: list[str] = []
                for name in WORKFLOW_BUCKETS:
                    if name in buckets:
                        continue
                    fallback = NEW_VIEW_BUCKETS.get(name, "")
                    if fallback and fallback in buckets:
                        buckets[name] = client.rename_bucket(
                            project,
                            board_view.id,
                            buckets.pop(fallback).id,
                            name,
                        )
                        renamed.append(name)
                    else:
                        buckets[name] = client.create_bucket(
                            project, board_view.id, name
                        )
                        created.append(name)
                default = buckets[WORKFLOW_BUCKETS[0]].id
                done = buckets[WORKFLOW_BUCKETS[-1]].id
                board_view = client.set_view_buckets(
                    project, board_view.id, default=default, done=done
                )
            payload = {
                "view": board_view.id,
                "buckets": {name: buckets[name].id for name in WORKFLOW_BUCKETS},
                "default_bucket": default,
                "done_bucket": done,
                "renamed_buckets": renamed,
                "created_buckets": created,
            }
            rows = [(str(board_view.id), f"view '{board_view.title}'")] + [
                (str(buckets[name].id), name) for name in WORKFLOW_BUCKETS
            ]
            _emit(payload, as_json, rows)
        except BoardError, ValidationError, OSError, ValueError:
            _fail()

    @backlog_app.command("import")
    def import_tickets(
        project: Annotated[int, typer.Option(help="Project id.")],
        view: Annotated[int, typer.Option(help="Kanban view id.")],
        bucket: Annotated[int, typer.Option(help="Bucket for new tickets.")],
        plan: Annotated[Path, typer.Option(help="Cycle plan document.")] = PLAN,
        dry_run: Annotated[
            bool, typer.Option("--dry-run", help="Report without writing.")
        ] = False,
        token_file: Annotated[
            Path | None, typer.Option(help="Private token file.")
        ] = None,
        base_url: Annotated[
            str, typer.Option(help="Loopback tunnel base URL.")
        ] = "http://127.0.0.1:3458",
        as_json: Annotated[bool, typer.Option("--json")] = False,
    ) -> None:
        """Create only the plan tickets missing from the board. Existing
        tasks are never touched and a duplicate key is an error, not fuzzy
        matching. `--dry-run` writes nothing."""
        try:
            tickets = load_plan_tickets(REPO_ROOT, plan)
            with _client(token_file, base_url) as client:
                keys = _board_keys(client.tasks(project))
                duplicates = sorted(key for key, count in keys.items() if count > 1)
                if duplicates:
                    err_console.print(
                        "[bold red]Board already has duplicate keys: "
                        f"{', '.join(duplicates)}[/bold red]"
                    )
                    raise typer.Exit(1)
                missing = [ticket for ticket in tickets if ticket.key not in keys]
                created: list[str] = []
                if not dry_run:
                    for ticket in missing:
                        record = client.create_task(
                            project,
                            title=f"{ticket.key} — {ticket.title}",
                            description=ticket_description(ticket, plan),
                        )
                        client.place_task(project, view, bucket, record.id)
                        created.append(ticket.key)
            payload = {
                "plan_tickets": len(tickets),
                "missing": [ticket.key for ticket in missing],
                "created": created,
                "dry_run": dry_run,
            }
            rows = [(ticket.key, ticket.title) for ticket in missing]
            _emit(payload, as_json, rows)
            if not as_json:
                action = "would be created" if dry_run else "created"
                console.print(
                    f"{len(missing)} ticket(s) {action}; "
                    f"{len(tickets) - len(missing)} already present."
                )
        except BoardError, ValidationError, OSError, ValueError:
            _fail()

    app.add_typer(backlog_app, name="backlog")
