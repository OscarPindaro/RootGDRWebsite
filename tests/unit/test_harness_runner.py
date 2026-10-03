import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from harness.test import runner, state


@pytest.fixture
def test_root(tmp_path: Path) -> Path:
    for suite in runner.TestSuite:
        directory = tmp_path / "tests" / suite.value
        directory.mkdir(parents=True)
        (directory / "test_selected.py").write_text(
            "def test_selected():\n    assert True\n\ndef test_other():\n    assert False\n"
        )
    return tmp_path


def test_parse_preserves_option_values_and_multiple_selectors() -> None:
    selection = runner.parse_arguments(
        [
            "tests/unit/test_first.py::test_one",
            "-k",
            "selected and not other",
            "tests/unit/test_second.py",
            "-x",
            "--maxfail",
            "2",
            "--tb=long",
            "-vv",
            "--capture",
            "tee-sys",
            "--durations=3",
            "--durations-min",
            "0.1",
            "-r",
            "fE",
            "--collect-only",
            "--showlocals",
            "--full-trace",
            "--disable-warnings",
            "--color=no",
        ]
    )

    assert selection.selectors == [
        "tests/unit/test_first.py::test_one",
        "tests/unit/test_second.py",
    ]
    assert selection.options.keyword == "selected and not other"
    assert selection.options.fail_fast
    assert selection.options.max_failures == 2
    assert selection.options.traceback == "long"
    assert selection.options.verbosity == 2
    assert selection.options.capture == "tee-sys"
    assert selection.options.durations == 3
    assert selection.options.durations_min == 0.1
    assert selection.options.report == "fE"
    assert selection.options.collect_only
    assert selection.options.show_locals
    assert selection.options.full_trace
    assert selection.options.disable_warnings
    assert selection.options.color == "no"


@pytest.mark.parametrize("value", ["tests/unit/nonexistent.py", "../outside", "-x"])
def test_keyword_values_are_not_selectors(value: str) -> None:
    selection = runner.parse_arguments([f"-k={value}"])
    assert selection.selectors == []
    assert selection.options.keyword == value


@pytest.mark.parametrize(
    "arguments",
    [
        ["--unknown"],
        ["-m", "e2e"],
        ["-c", "other.ini"],
        ["-o", "addopts=tests/e2e"],
        ["--override-ini=testpaths=tests/e2e"],
        ["--rootdir", ".."],
        ["--confcutdir", ".."],
        ["--noconftest"],
        ["--pyargs", "package"],
        ["-p", "plugin"],
        ["--base-url", "http://production"],
        ["--fresh"],
        ["--maxfail", "0"],
        ["--maxfail", "no"],
        ["--durations", "-1"],
        ["--durations-min", "nan"],
        ["--verbosity", "-1"],
        ["--verb", "2"],
        ["--capture", "invalid"],
        ["--tb", "invalid"],
        ["-k"],
        ["--durations"],
    ],
)
def test_invalid_or_boundary_overriding_options_are_rejected(
    arguments: list[str],
) -> None:
    with pytest.raises(ValueError):
        runner.parse_arguments(arguments)


@pytest.mark.parametrize("suite", list(runner.TestSuite))
def test_selectors_replace_defaults_and_keep_markers(test_root: Path, suite) -> None:
    selector = f"tests/{suite.value}/test_selected.py::test_selected"
    with (
        patch.object(state, "worktree_root", return_value=test_root),
        patch.object(state, "read", return_value=None),
        patch.object(
            runner.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 0, "ok", ""),
        ) as process,
    ):
        result = runner.run(suite, [selector])

    assert f"tests/{suite.value}" not in result.command
    assert str(test_root / selector) in result.command
    if suite in (runner.TestSuite.INTEGRATION, runner.TestSuite.E2E):
        assert result.command[3:5] == ["-m", suite.value]
    process.assert_called_once()
    assert process.call_args.kwargs["cwd"] == test_root
    assert "shell" not in process.call_args.kwargs


@pytest.mark.parametrize("suite", list(runner.TestSuite))
def test_no_arguments_keep_defaults(test_root: Path, suite) -> None:
    with (
        patch.object(state, "worktree_root", return_value=test_root),
        patch.object(state, "read", return_value=None),
        patch.object(
            runner.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 0, "", ""),
        ),
    ):
        result = runner.run(suite)
    target = (
        [f"tests/{suite.value}"]
        if suite in (runner.TestSuite.UNIT, runner.TestSuite.FRONTEND)
        else ["-m", suite.value]
    )
    assert result.command == ["uv", "run", "pytest", *target, "-q", "--tb=short"]


@pytest.mark.parametrize(
    "selector",
    [
        "../outside.py",
        "tests/unit/../../outside.py",
        "tests/unit/../frontend/test_selected.py",
        "tests/frontend/test_selected.py",
        "tests",
        "tests/unit/missing.py",
        "tests/unit/escape.py",
        "tests/unit/cross_suite.py",
    ],
)
def test_invalid_selectors_fail_before_subprocess(
    test_root: Path, selector: str
) -> None:
    outside = test_root / "outside.py"
    outside.write_text("def test_outside(): pass\n")
    (test_root / "tests/unit/escape.py").symlink_to(outside)
    (test_root / "tests/unit/cross_suite.py").symlink_to(
        test_root / "tests/frontend/test_selected.py"
    )
    with (
        patch.object(state, "worktree_root", return_value=test_root),
        patch.object(runner.subprocess, "run") as process,
        pytest.raises(ValueError),
    ):
        runner.run(runner.TestSuite.UNIT, [selector])
    process.assert_not_called()


def test_symlinked_suite_cannot_escape_tests(test_root: Path) -> None:
    suite = test_root / "tests/unit"
    (suite / "test_selected.py").unlink()
    suite.rmdir()
    suite.symlink_to(test_root / "tests/frontend", target_is_directory=True)
    with (
        patch.object(state, "worktree_root", return_value=test_root),
        patch.object(runner.subprocess, "run") as process,
        pytest.raises(ValueError),
    ):
        runner.run(runner.TestSuite.UNIT, ["tests/unit/test_selected.py"])
    process.assert_not_called()


@pytest.mark.parametrize("suite", [runner.TestSuite.INTEGRATION, runner.TestSuite.E2E])
def test_active_suite_configuration_is_preserved(test_root: Path, suite) -> None:
    config = state.ConfigState(
        backup=test_root / "backup.yaml",
        env=test_root / "test.env",
        integration_config=test_root / "integration.yaml",
        integration_env=test_root / "integration.env",
        e2e_config=test_root / "e2e.docker.yaml",
        e2e_env=test_root / "e2e.env",
        e2e_local_config=test_root / "e2e.yaml",
    )
    config.integration_env.write_text(
        "DATABASE__DB=integration_only\nPYTEST_ADDOPTS=-m unit\n"
    )
    config.e2e_env.write_text("DATABASE__DB=e2e_only\nPYTEST_ADDOPTS=-m unit\n")
    active = state.EnvironmentState(
        worktree=test_root,
        mode=state.EnvironmentMode.DOCKER,
        status="ready",
        created_at=datetime.now(UTC),
        compose_project="pytest-fixture",
        ports=state.PortState(database=15432, backend=18000),
        config=config,
    )
    with (
        patch.object(state, "worktree_root", return_value=test_root),
        patch.object(state, "read", return_value=active),
        patch.dict(os.environ, {"PYTEST_ADDOPTS": "-m unit -c other.ini"}),
        patch.object(
            runner.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 0, "", ""),
        ) as process,
    ):
        runner.run(suite, [f"tests/{suite.value}/test_selected.py"])
    environment = process.call_args.kwargs["env"]
    env_file, config_file = runner._suite_config(suite, active)
    assert environment["ENV_FILE"] == str(env_file)
    assert environment["YAML_CONFIG_FILE"] == str(config_file)
    assert environment["DATABASE__DB"] == f"{suite.value}_only"
    assert not environment.get("PYTEST_ADDOPTS")


@pytest.mark.parametrize("suite", [runner.TestSuite.UNIT, runner.TestSuite.FRONTEND])
@pytest.mark.parametrize(
    ("arguments", "code", "summary"),
    [
        (["::test_selected"], 0, "1 passed"),
        (["", "-k", "selected and not other"], 0, "1 passed, 1 deselected"),
        (["::test_other"], 1, "1 failed"),
        (["", "-k", "absent"], 5, "2 deselected"),
        (["", "-k", "selected and"], 4, ""),
        (["::test_missing"], 4, "no tests ran"),
        (["", "--collect-only"], 0, "2 tests collected"),
    ],
)
def test_actual_pytest_runs_only_selected_cases(
    test_root: Path, suite, arguments, code, summary
) -> None:
    invoke = subprocess.run

    def isolated_pytest(command: list[str], **kwargs):
        assert command[:3] == ["uv", "run", "pytest"]
        kwargs["env"]["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        return invoke([sys.executable, "-m", "pytest", *command[3:]], **kwargs)

    selector = f"tests/{suite.value}/test_selected.py{arguments[0]}"
    selection = runner.parse_arguments([selector, *arguments[1:]])
    with (
        patch.object(state, "worktree_root", return_value=test_root),
        patch.object(state, "read", return_value=None),
        patch.object(runner.subprocess, "run", side_effect=isolated_pytest),
    ):
        result = runner.run(suite, selection.selectors, selection.options)
    assert result.return_code == code
    assert summary in result.stdout


def test_all_supported_options_are_assembled_without_value_injection(
    test_root: Path,
) -> None:
    selection = runner.parse_arguments(
        [
            "-k=--rootdir=../outside",
            "--maxfail=2",
            "--exitfirst",
            "--verbosity=2",
            "--tb=long",
            "-s",
            "--co",
            "--durations=0",
            "--durations-min=0.1",
            "-r=--override-ini=addopts=tests/e2e",
            "-l",
            "--full-trace",
            "--disable-warnings",
            "--color=no",
        ]
    )
    with (
        patch.object(state, "worktree_root", return_value=test_root),
        patch.object(state, "read", return_value=None),
        patch.object(
            runner.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 0, "", ""),
        ),
    ):
        result = runner.run(runner.TestSuite.UNIT, options=selection.options)
    assert result.command == [
        "uv",
        "run",
        "pytest",
        "tests/unit",
        "-k=--rootdir=../outside",
        "--maxfail=2",
        "-x",
        "-vv",
        "--tb=long",
        "--capture=no",
        "--collect-only",
        "--durations=0",
        "--durations-min=0.1",
        "-r=--override-ini=addopts=tests/e2e",
        "--showlocals",
        "--full-trace",
        "--disable-warnings",
        "--color=no",
    ]


def test_actual_pytest_preserves_collection_errors(test_root: Path) -> None:
    (test_root / "tests/unit/test_selected.py").write_text("def syntax_error(\n")
    invoke = subprocess.run

    def isolated_pytest(command: list[str], **kwargs):
        kwargs["env"]["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        return invoke([sys.executable, "-m", "pytest", *command[3:]], **kwargs)

    with (
        patch.object(state, "worktree_root", return_value=test_root),
        patch.object(state, "read", return_value=None),
        patch.object(runner.subprocess, "run", side_effect=isolated_pytest),
    ):
        result = runner.run(runner.TestSuite.UNIT, ["tests/unit/test_selected.py"])
    assert result.return_code == 2
    assert "SyntaxError" in result.stdout
