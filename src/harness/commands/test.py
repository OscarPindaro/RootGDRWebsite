"""Test commands — `harness test ...`."""

from __future__ import annotations

import subprocess
from typing import Annotated

import typer
from rich.console import Console

from ..test import environment, runner, state
from ..test.server import serve as serve_test

err_console = Console(stderr=True)
test_app = typer.Typer(
    no_args_is_help=True, help="Run tests against active environments."
)


def _run(command: list[str]) -> None:
    result = subprocess.run(command)
    if result.returncode:
        raise typer.Exit(result.returncode)


PytestArguments = Annotated[
    list[str] | None,
    typer.Argument(
        help=(
            "Pytest arguments after --: suite-local paths/node IDs, -k, -x/--exitfirst, "
            "--maxfail, -q, -v/--verbosity, --tb, -s/--capture, --collect-only, --durations, "
            "--durations-min, -r, --showlocals, --full-trace, --disable-warnings, --color. "
            "Configuration, marker, plugin and environment overrides are rejected."
        )
    ),
]


def _parse_arguments(
    suite: runner.TestSuite, arguments: list[str] | None
) -> runner.PytestSelection:
    try:
        return runner.parse_arguments(arguments or [], suite)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error


def _run_suite(suite: runner.TestSuite, selection: runner.PytestSelection) -> None:
    result = runner.run(suite, selection.selectors, selection.options)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        err_console.print(result.stderr, end="")
    if result.return_code:
        raise typer.Exit(result.return_code)


def _require_environment(
    mode: state.EnvironmentMode | None = None,
) -> state.EnvironmentState:
    environment_state, _ = environment.status()
    if environment_state is None:
        raise typer.BadParameter("No active environment for this worktree.")
    if mode is not None and environment_state.mode != mode:
        raise typer.BadParameter(
            f"This command requires a {mode.value} environment, found {environment_state.mode.value}."
        )
    return environment_state


@test_app.command()
def serve() -> None:
    """Start the test-harness MCP server over stdio."""
    serve_test()


@test_app.command()
def unit(pytest_args: PytestArguments = None) -> None:
    """Run unit tests without an environment."""
    _run_suite(
        runner.TestSuite.UNIT, _parse_arguments(runner.TestSuite.UNIT, pytest_args)
    )


@test_app.command()
def frontend(pytest_args: PytestArguments = None) -> None:
    """Run component tests: real JinjaX components in Chromium, no backend."""
    _run_suite(
        runner.TestSuite.FRONTEND,
        _parse_arguments(runner.TestSuite.FRONTEND, pytest_args),
    )


@test_app.command()
def integration(pytest_args: PytestArguments = None) -> None:
    """Run integration tests against the active test database."""
    _require_environment()
    _run_suite(
        runner.TestSuite.INTEGRATION,
        _parse_arguments(runner.TestSuite.INTEGRATION, pytest_args),
    )


@test_app.command(name="external_integrations")
def external_integrations(pytest_args: PytestArguments = None) -> None:
    """Run the local-only suites: containers, Ansible, restic and the board.

    These are never part of a default run and never part of CI: they build and
    start real containers and need the pinned images on the machine.
    """
    _require_environment()
    _run_suite(
        runner.TestSuite.EXTERNAL_INTEGRATIONS,
        _parse_arguments(runner.TestSuite.EXTERNAL_INTEGRATIONS, pytest_args),
    )


@test_app.command()
def e2e(
    fresh: Annotated[
        bool,
        typer.Option(
            "--fresh",
            help="Recreate the active test database and uploads before running.",
        ),
    ] = False,
    pytest_args: PytestArguments = None,
) -> None:
    """Run E2E tests against the active Docker environment."""
    _require_environment(state.EnvironmentMode.DOCKER)
    selection = _parse_arguments(runner.TestSuite.E2E, pytest_args)
    if fresh:
        try:
            environment.reset_e2e_environment()
        except environment.EnvironmentError as error:
            err_console.print(f"[bold red]{error}[/bold red]")
            raise typer.Exit(1) from error
    _run_suite(runner.TestSuite.E2E, selection)


@test_app.command()
def run(
    command: Annotated[
        list[str], typer.Argument(help="Command to run after environment startup.")
    ],
    mode: Annotated[
        state.EnvironmentMode, typer.Option()
    ] = state.EnvironmentMode.LOCAL,
) -> None:
    """Create an environment, run a command, and always tear it down."""
    if state.read() is not None:
        raise typer.BadParameter(
            "Teardown the active environment before using test run."
        )
    try:
        environment.up(mode)
        _run(command)
    except environment.EnvironmentError as error:
        err_console.print(f"[bold red]{error}[/bold red]")
        raise typer.Exit(1) from error
    finally:
        try:
            environment.teardown()
        except environment.EnvironmentError as error:
            err_console.print(f"[bold red]{error}[/bold red]")
