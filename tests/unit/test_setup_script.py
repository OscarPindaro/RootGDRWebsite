"""The setup script's harness path (REQ-0011/T08).

The script is exercised with stub `uv` and `npm` binaries, so the test is
offline and fast while still proving what it runs, from where, and in which
directory.
"""

import os
import subprocess
from pathlib import Path

from harness.browser_runtime import REPO_ROOT


def test_setup_harness_installs_locked_node_deps_from_any_cwd(tmp_path: Path) -> None:
    stubs = tmp_path / "bin"
    stubs.mkdir()
    log = tmp_path / "calls.log"
    for name in ("uv", "npm"):
        stub = stubs / name
        stub.write_text(
            '#!/usr/bin/env bash\nprintf "%s %s\\n" "$PWD" "$*" >> "$STUB_LOG"\n'
        )
        stub.chmod(0o755)

    result = subprocess.run(
        ["bash", str(REPO_ROOT / "setup.sh"), "--harness"],
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": f"{stubs}:{os.environ['PATH']}",
            "STUB_LOG": str(log),
            "VIRTUAL_ENV": str(tmp_path / "venv"),
        },
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    calls = log.read_text(encoding="utf-8").splitlines()
    assert calls, "the setup script ran nothing"
    assert all(call.startswith(str(REPO_ROOT)) for call in calls)
    assert any(call.endswith(" ci") for call in calls)
    assert any("run harness browsers" in call for call in calls)
    assert not any("playwright install" in call for call in calls)
    assert not any(call.endswith(" install") for call in calls if "npm" in call)


def test_accessibility_scan_fails_instead_of_skipping_without_axe() -> None:
    source = (REPO_ROOT / "tests/e2e/test_accessibility.py").read_text("utf-8")
    assert "axe-core is not installed" in source
    assert "skip" not in source
