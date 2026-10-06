import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from harness.commands import test as commands
from harness.test import runner, state

cli = CliRunner()


@pytest.mark.parametrize("suite", list(runner.TestSuite))
def test_trailing_tokens_are_forwarded_for_every_suite(tmp_path: Path, suite) -> None:
    directory = tmp_path / "tests" / suite.value
    directory.mkdir(parents=True)
    (directory / "test_one.py").write_text("def test_one(): pass\n")
    (directory / "test_two.py").write_text("def test_two(): pass\n")
    tokens = [
        f"tests/{suite.value}/test_one.py::test_one",
        "-k",
        "one or two",
        f"tests/{suite.value}/test_two.py",
        "-x",
        "--tb=long",
        "-vv",
    ]
    with (
        patch.object(commands, "_require_environment") as require,
        patch.object(state, "worktree_root", return_value=tmp_path),
        patch.object(state, "read", return_value=None),
        patch.object(
            runner.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 0, "selected output\n", ""),
        ) as process,
    ):
        result = cli.invoke(commands.test_app, [suite.value, "--", *tokens])
    assert result.exit_code == 0, result.output
    assert "selected output" in result.output
    command = process.call_args.args[0]
    assert command[command.index("-k") + 1] == "one or two"
    assert str(directory / "test_one.py") + "::test_one" in command
    assert str(directory / "test_two.py") in command
    assert f"tests/{suite.value}" not in command
    assert "--tb=long" in command
    assert "-vv" in command
    assert "-x" in command
    if suite == runner.TestSuite.E2E:
        require.assert_called_once_with(state.EnvironmentMode.DOCKER)
    elif suite in (
        runner.TestSuite.INTEGRATION,
        runner.TestSuite.EXTERNAL_INTEGRATIONS,
    ):
        require.assert_called_once_with()
    else:
        require.assert_not_called()


@pytest.mark.parametrize("suite", list(runner.TestSuite))
@pytest.mark.parametrize("code", [0, 1, 2, 3, 4, 5])
def test_pytest_exit_codes_and_output_are_preserved(suite, code: int) -> None:
    result = runner.TestResult(
        suite=suite,
        command=["uv", "run", "pytest"],
        return_code=code,
        stdout="pytest stdout\n",
        stderr="pytest stderr\n",
    )
    with (
        patch.object(commands, "_require_environment"),
        patch.object(runner, "run", return_value=result),
    ):
        outcome = cli.invoke(commands.test_app, [suite.value])
    assert outcome.exit_code == code
    assert "pytest stdout" in outcome.output
    assert "pytest stderr" in outcome.output


@pytest.mark.parametrize("suite", list(runner.TestSuite))
def test_unknown_options_fail_without_running_pytest(suite) -> None:
    with (
        patch.object(commands, "_require_environment"),
        patch.object(runner, "run") as process,
    ):
        outcome = cli.invoke(commands.test_app, [suite.value, "--", "--unknown"])
    assert outcome.exit_code == 2
    assert "unsupported" in outcome.output.lower()
    process.assert_not_called()


@pytest.mark.parametrize("suite", ["unit", "frontend", "integration"])
def test_fresh_is_e2e_only(suite: str) -> None:
    with patch.object(commands.environment, "reset_e2e_environment") as reset:
        outcome = cli.invoke(commands.test_app, [suite, "--fresh"])
    assert outcome.exit_code == 2
    reset.assert_not_called()


def test_fresh_after_separator_is_not_a_harness_option() -> None:
    with (
        patch.object(commands, "_require_environment"),
        patch.object(commands.environment, "reset_e2e_environment") as reset,
        patch.object(runner, "run") as process,
    ):
        outcome = cli.invoke(commands.test_app, ["e2e", "--", "--fresh"])
    assert outcome.exit_code == 2
    reset.assert_not_called()
    process.assert_not_called()


@pytest.mark.parametrize(
    "arguments", [["--unknown"], ["tests/unit/test_wrong_suite.py"]]
)
def test_invalid_arguments_do_not_reset_fresh_environment(arguments: list[str]) -> None:
    with (
        patch.object(commands, "_require_environment"),
        patch.object(commands.environment, "reset_e2e_environment") as reset,
        patch.object(runner, "run") as process,
    ):
        outcome = cli.invoke(commands.test_app, ["e2e", "--fresh", "--", *arguments])
    assert outcome.exit_code == 2
    reset.assert_not_called()
    process.assert_not_called()


def test_fresh_resets_before_forwarding_valid_pytest_options() -> None:
    calls = []
    result = runner.TestResult(
        suite=runner.TestSuite.E2E, command=[], return_code=0, stdout="", stderr=""
    )
    with (
        patch.object(
            commands,
            "_require_environment",
            side_effect=lambda mode: calls.append("require"),
        ),
        patch.object(
            commands.environment,
            "reset_e2e_environment",
            side_effect=lambda: calls.append("reset"),
        ),
        patch.object(
            runner, "run", side_effect=lambda *args: calls.append("run") or result
        ) as run,
    ):
        outcome = cli.invoke(
            commands.test_app,
            ["e2e", "--fresh", "--", "-k", "face_pickers", "-x", "--tb=long"],
        )
    assert outcome.exit_code == 0, outcome.output
    assert calls == ["require", "reset", "run"]
    assert run.call_args.args[2].keyword == "face_pickers"
    assert run.call_args.args[2].fail_fast
    assert run.call_args.args[2].traceback == "long"


@pytest.mark.parametrize("suite", ["integration", "e2e"])
def test_environment_checks_cannot_be_bypassed(suite: str) -> None:
    with (
        patch.object(commands.environment, "status", return_value=(None, "inactive")),
        patch.object(runner, "run") as process,
    ):
        outcome = cli.invoke(commands.test_app, [suite, "--", "-k", "selected"])
    assert outcome.exit_code == 2
    assert "No active environment" in outcome.output
    process.assert_not_called()


def test_e2e_rejects_local_environment() -> None:
    active = state.EnvironmentState.model_construct(mode=state.EnvironmentMode.LOCAL)
    with (
        patch.object(commands.environment, "status", return_value=(active, "local")),
        patch.object(runner, "run") as process,
    ):
        outcome = cli.invoke(commands.test_app, ["e2e", "--", "-k", "selected"])
    assert outcome.exit_code == 2
    assert "requires a docker environment" in outcome.output
    process.assert_not_called()
