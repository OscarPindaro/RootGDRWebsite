import argparse
import os
import subprocess
from enum import Enum
from pathlib import Path
from typing import Literal

from dotenv import dotenv_values
from pydantic import BaseModel, Field

from . import state


class TestSuite(str, Enum):
    UNIT = "unit"
    FRONTEND = "frontend"
    INTEGRATION = "integration"
    E2E = "e2e"


class PytestOptions(BaseModel):
    keyword: str | None = None
    max_failures: int | None = Field(default=None, ge=1)
    fail_fast: bool = False
    quiet: bool = True
    traceback: Literal["auto", "long", "short", "line", "native", "no"] = "short"
    verbosity: int = Field(default=0, ge=0)
    capture: Literal["fd", "sys", "no", "tee-sys"] | None = None
    collect_only: bool = False
    durations: int | None = Field(default=None, ge=0)
    durations_min: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    report: str | None = None
    show_locals: bool = False
    full_trace: bool = False
    disable_warnings: bool = False
    color: Literal["yes", "no", "auto"] | None = None


class PytestSelection(BaseModel):
    selectors: list[str] = Field(default_factory=list)
    options: PytestOptions = Field(default_factory=PytestOptions)


class _PytestParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(
            f"Invalid or unsupported pytest arguments: {message}\n"
            "Only selection, failure limits, collection and reporting options are supported; "
            "configuration, marker, plugin and environment overrides are not allowed.\n"
            f"{self.format_usage()}"
        )


def parse_arguments(
    arguments: list[str], suite: TestSuite | None = None
) -> PytestSelection:
    """Parse a bounded pytest interface without allowing suite/config overrides."""
    parser = _PytestParser(prog="pytest", add_help=False, allow_abbrev=False)
    parser.add_argument("selectors", nargs="*")
    parser.add_argument("-k", dest="keyword")
    parser.add_argument("--maxfail", dest="max_failures", type=int)
    parser.add_argument("-x", "--exitfirst", dest="fail_fast", action="store_true")
    parser.add_argument("-q", "--quiet", action="store_true", default=True)
    parser.add_argument("-v", "--verbose", dest="verbosity", action="count", default=0)
    parser.add_argument("--verbosity", type=int)
    parser.add_argument("--tb", dest="traceback", default="short")
    parser.add_argument("-s", dest="capture", action="store_const", const="no")
    parser.add_argument("--capture")
    parser.add_argument(
        "--collect-only", "--co", dest="collect_only", action="store_true"
    )
    parser.add_argument("--durations", type=int)
    parser.add_argument("--durations-min", dest="durations_min", type=float)
    parser.add_argument("-r", dest="report")
    parser.add_argument("-l", "--showlocals", dest="show_locals", action="store_true")
    parser.add_argument("--full-trace", dest="full_trace", action="store_true")
    parser.add_argument(
        "--disable-warnings", dest="disable_warnings", action="store_true"
    )
    parser.add_argument("--color")
    parsed = parser.parse_intermixed_args(arguments)
    return PytestSelection(
        selectors=(
            _selectors(state.worktree_root(), suite, parsed.selectors)
            if suite is not None
            else parsed.selectors
        ),
        options=PytestOptions.model_validate(vars(parsed)),
    )


class TestResult(BaseModel):
    suite: TestSuite
    command: list[str]
    return_code: int
    stdout: str
    stderr: str


def run(
    suite: TestSuite,
    selectors: list[str] | None = None,
    options: PytestOptions | None = None,
) -> TestResult:
    root = state.worktree_root()
    options = options or PytestOptions()
    command = ["uv", "run", "pytest"]
    if suite in (TestSuite.INTEGRATION, TestSuite.E2E):
        command.extend(["-m", suite.value])
    if selectors:
        command.extend(_selectors(root, suite, selectors))
    elif suite in (TestSuite.UNIT, TestSuite.FRONTEND):
        command.append(f"tests/{suite.value}")
    if options.keyword:
        if options.keyword.startswith("-"):
            command.append(f"-k={options.keyword}")
        else:
            command.extend(["-k", options.keyword])
    if options.max_failures:
        command.append(f"--maxfail={options.max_failures}")
    if options.fail_fast:
        command.append("-x")
    if options.verbosity:
        command.append("-" + "v" * options.verbosity)
    elif options.quiet:
        command.append("-q")
    command.append(f"--tb={options.traceback}")
    if options.capture is not None:
        command.append(f"--capture={options.capture}")
    if options.collect_only:
        command.append("--collect-only")
    if options.durations is not None:
        command.append(f"--durations={options.durations}")
    if options.durations_min is not None:
        command.append(f"--durations-min={options.durations_min}")
    if options.report is not None:
        command.append(f"-r={options.report}")
    if options.show_locals:
        command.append("--showlocals")
    if options.full_trace:
        command.append("--full-trace")
    if options.disable_warnings:
        command.append("--disable-warnings")
    if options.color is not None:
        command.append(f"--color={options.color}")
    process_environment = os.environ.copy()
    environment_state = state.read(root)
    if environment_state is not None and suite in (
        TestSuite.INTEGRATION,
        TestSuite.E2E,
    ):
        env_file, config_file = _suite_config(suite, environment_state)
        process_environment.update(
            {
                key: value
                for key, value in dotenv_values(env_file).items()
                if value is not None
            }
        )
        process_environment.update(
            ENV_FILE=str(env_file),
            YAML_CONFIG_FILE=str(config_file),
        )
    process_environment.pop("PYTEST_ADDOPTS", None)
    result = subprocess.run(
        command,
        cwd=root,
        capture_output=True,
        text=True,
        env=process_environment,
    )
    return TestResult(
        suite=suite,
        command=command,
        return_code=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def _suite_config(
    suite: TestSuite, environment_state: state.EnvironmentState
) -> tuple[Path, Path]:
    """Env and YAML config for a suite: integration in-process, E2E against Docker."""
    config = environment_state.config
    if suite == TestSuite.INTEGRATION:
        return config.integration_env, config.integration_config
    return config.e2e_env, config.e2e_local_config


def _selectors(root: Path, suite: TestSuite, selectors: list[str]) -> list[str]:
    tests = root.resolve() / "tests" / suite.value
    valid = []
    for selector in selectors:
        path, _, node_id = selector.partition("::")
        candidate = (root / path).resolve()
        try:
            candidate.relative_to(tests)
        except ValueError as error:
            raise ValueError(
                f"Test selector must be inside tests/{suite.value}/: {selector}"
            ) from error
        if not candidate.exists():
            raise ValueError(f"Test selector does not exist: {selector}")
        valid.append(f"{candidate}{'::' + node_id if node_id else ''}")
    return valid
