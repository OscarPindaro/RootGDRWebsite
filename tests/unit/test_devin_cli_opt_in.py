import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.external_integrations.test_devin_cli_workers import Export

pytestmark = [
    pytest.mark.unit,
    pytest.mark.skipif(
        sys.platform != "linux", reason="The live CLI suite is Linux-only."
    ),
]

ROOT = Path(__file__).resolve().parents[2]
LIVE_TEST = "tests/external_integrations/test_devin_cli_workers.py"


def test_model_export_accepts_tool_free_atif_steps() -> None:
    exported = Export.model_validate_json(
        '{"session_id":"fixture","agent":{"model_name":"DeepSeek V4.1 Flash High"},'
        '"steps":[{"model_name":null,"tool_calls":null},'
        '{"model_name":"deepseek-v4-1-flash-1017-high","tool_calls":[]}]}'
    )
    assert exported.session_id == "fixture"
    assert not any(step.tool_calls for step in exported.steps)


@pytest.mark.parametrize(
    ("enabled", "ci", "collect_only", "should_invoke"),
    [
        (False, False, False, False),
        (True, True, False, False),
        (True, False, True, False),
        (True, False, False, True),
    ],
)
def test_live_cli_requires_explicit_local_execution(
    tmp_path: Path, enabled: bool, ci: bool, collect_only: bool, should_invoke: bool
) -> None:
    binary = tmp_path / "devin"
    invoked = tmp_path / "invoked"
    binary.write_text(
        f"#!{sys.executable}\n"
        "from pathlib import Path\n"
        f"Path({str(invoked)!r}).write_text('called')\n"
        "raise SystemExit(86)\n"
    )
    binary.chmod(0o700)
    environment = os.environ.copy()
    environment["PATH"] = str(tmp_path) + os.pathsep + environment["PATH"]
    environment.pop("PYTEST_ADDOPTS", None)
    environment.pop("CI", None)
    if ci:
        environment["CI"] = "true"
    command = [
        sys.executable,
        "-m",
        "pytest",
        LIVE_TEST,
        "-m",
        "devin_cli_e2e",
        "-q",
        "--tb=short",
    ]
    if enabled:
        command.append("--run-devin-cli-e2e")
    if collect_only:
        command.append("--collect-only")
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert invoked.exists() is should_invoke, result.stdout + result.stderr
    if should_invoke:
        assert result.returncode != 0, "The sentinel CLI must fail authentication."
        assert "Devin CLI exited 86" in result.stdout
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        assert (
            "collected" in result.stdout if collect_only else "skipped" in result.stdout
        )
