"""Read and filter structured logs from a harness Compose stack."""

from __future__ import annotations

import enum
import json
from collections.abc import Iterable
from typing import Annotated, Any

import typer

from ..dev import compose as dev_compose
from ..dev import state as dev_state
from ..test import compose as test_compose
from ..test import state as test_state


class Stack(str, enum.Enum):
    TEST = "test"
    DEV = "dev"


class LogsError(RuntimeError):
    """Raised when the selected stack is not active."""


def _payload(line: str) -> dict[str, Any] | None:
    """Parse a JSON log object, tolerating a Compose service prefix."""
    candidates = (line, line.partition(" | ")[2])
    for candidate in candidates:
        if not candidate:
            continue
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def filter_lines(
    lines: Iterable[str],
    *,
    request_id: str | None = None,
    trace_id: str | None = None,
) -> list[str]:
    """Return lines matching correlation fields.

    Non-JSON output is useful for database and startup diagnostics, so it is
    retained unless a correlation field filter makes matching impossible.
    """
    filtered: list[str] = []
    for line in lines:
        payload = _payload(line)
        if request_id is not None and (
            payload is None or payload.get("request_id") != request_id
        ):
            continue
        if trace_id is not None and (
            payload is None or payload.get("trace_id") != trace_id
        ):
            continue
        filtered.append(line)
    return filtered


def compose_logs(stack: Stack, service: str | None = None) -> str:
    """Obtain logs through the selected stack's existing Compose API."""
    root = test_state.worktree_root()
    args = ["logs", "--no-color", "--no-log-prefix"]
    if service is not None:
        service = service.strip()
        if not service:
            raise LogsError("Service must not be empty")
        args.append(service)

    if stack == Stack.TEST:
        active_test = test_state.read(root)
        if active_test is None:
            raise LogsError("No test stack. Run `harness env up` first.")
        return test_compose._run(active_test, *args)

    active_dev = dev_state.read(root)
    if active_dev is None:
        raise LogsError("No development stack. Run `harness dev up` first.")
    return dev_compose.run(active_dev, *args)


def logs(
    stack: Annotated[
        Stack, typer.Option("--stack", help="Stack to inspect: test or dev.")
    ] = Stack.TEST,
    request_id: Annotated[
        str | None, typer.Option("--request-id", help="Match a request_id field.")
    ] = None,
    trace_id: Annotated[
        str | None, typer.Option("--trace-id", help="Match a trace_id field.")
    ] = None,
    service: Annotated[
        str | None, typer.Option("--service", help="Limit Compose logs to one service.")
    ] = None,
) -> None:
    """Print logs from an active test or development stack."""
    try:
        output = compose_logs(stack, service)
    except (LogsError, test_compose.ComposeError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(1) from error

    for line in filter_lines(
        output.splitlines(), request_id=request_id, trace_id=trace_id
    ):
        typer.echo(line)


def register_command(app: typer.Typer) -> None:
    """Register the command when the main harness CLI opts into it."""
    app.command(name="logs")(logs)


app = typer.Typer(add_completion=False)
app.command(name="logs")(logs)


if __name__ == "__main__":
    app()
