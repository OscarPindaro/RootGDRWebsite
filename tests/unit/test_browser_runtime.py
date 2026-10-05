import os
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from harness import browser_runtime
from harness.cli import app as harness_app
from harness.commands import browsers as browsers_command

cli = CliRunner()

EXECUTABLES = {
    "chromium": "chrome",
    "chromium-headless-shell": "chrome-headless-shell",
}


def complete_layout(directory: Path) -> None:
    for name, revision in browser_runtime.required_revisions().items():
        payload = directory / f"{name.replace('-', '_')}-{revision}" / "payload"
        payload.mkdir(parents=True)
        (payload / EXECUTABLES[name]).write_text("")


def test_browsers_path_honours_an_explicit_override(monkeypatch, tmp_path):
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path / "custom"))
    assert browser_runtime.browsers_path() == tmp_path / "custom"
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", "   ")
    assert browser_runtime.browsers_path() == browser_runtime.DEFAULT_BROWSERS_PATH


def test_ensure_browsers_path_defaults_without_clobbering(monkeypatch, tmp_path):
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    assert (
        browser_runtime.ensure_browsers_path() == browser_runtime.DEFAULT_BROWSERS_PATH
    )
    assert os.environ["PLAYWRIGHT_BROWSERS_PATH"] == str(
        browser_runtime.DEFAULT_BROWSERS_PATH
    )
    override = tmp_path / "override"
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(override))
    assert browser_runtime.ensure_browsers_path() == override


def test_missing_browsers_reports_revisions_and_accepts_a_complete_layout(tmp_path):
    expected = sorted(
        f"{name}-{revision}"
        for name, revision in browser_runtime.required_revisions().items()
    )
    assert browser_runtime.missing_browsers(tmp_path) == expected
    complete_layout(tmp_path)
    assert browser_runtime.missing_browsers(tmp_path) == []


def test_browsers_skips_installation_when_the_revision_is_complete(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(browsers_command, "ensure_browsers_path", lambda: tmp_path)
    monkeypatch.setattr(browsers_command, "missing_browsers", lambda *_: [])
    monkeypatch.setattr(browsers_command, "_launch_problem", lambda: None)
    monkeypatch.setattr(
        browsers_command.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("no install")),
    )
    result = cli.invoke(harness_app, ["browsers"])
    assert result.exit_code == 0, result.output
    assert "is installed" in result.stdout


def test_browsers_installs_missing_revisions_and_verifies(monkeypatch, tmp_path):
    monkeypatch.setattr(browsers_command, "ensure_browsers_path", lambda: tmp_path)
    state = {"missing": ["chromium-1234"]}
    monkeypatch.setattr(
        browsers_command, "missing_browsers", lambda *_: state["missing"]
    )
    monkeypatch.setattr(browsers_command, "_launch_problem", lambda: None)
    seen: dict[str, object] = {}

    def fake_run(command, env=None):
        seen["command"] = command
        seen["env"] = env
        state["missing"] = []
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(browsers_command.subprocess, "run", fake_run)
    result = cli.invoke(harness_app, ["browsers"])
    assert result.exit_code == 0, result.output
    assert seen["command"][-1] == "chromium"
    assert seen["env"]["PLAYWRIGHT_BROWSERS_PATH"] == str(tmp_path)


def test_browsers_with_deps_asks_for_os_packages(monkeypatch, tmp_path):
    monkeypatch.setattr(browsers_command, "ensure_browsers_path", lambda: tmp_path)
    state = {"missing": ["chromium-1234"]}
    monkeypatch.setattr(
        browsers_command, "missing_browsers", lambda *_: state["missing"]
    )
    monkeypatch.setattr(browsers_command, "_launch_problem", lambda: None)
    seen: dict[str, object] = {}

    def fake_run(command, env=None):
        seen["command"] = command
        state["missing"] = []
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(browsers_command.subprocess, "run", fake_run)
    result = cli.invoke(harness_app, ["browsers", "--with-deps"])
    assert result.exit_code == 0, result.output
    assert seen["command"][-2:] == ["chromium", "--with-deps"]


def test_browsers_reports_missing_os_libraries_distinctly(monkeypatch, tmp_path):
    monkeypatch.setattr(browsers_command, "ensure_browsers_path", lambda: tmp_path)
    monkeypatch.setattr(browsers_command, "missing_browsers", lambda *_: [])
    monkeypatch.setattr(browsers_command, "_launch_problem", lambda: "os-libraries")
    result = cli.invoke(harness_app, ["browsers"])
    assert result.exit_code == 1
    output = result.stdout + result.stderr
    assert "OS libraries" in output
    assert "--with-deps" in output


def test_browsers_fails_on_an_incomplete_installation(monkeypatch, tmp_path):
    monkeypatch.setattr(browsers_command, "ensure_browsers_path", lambda: tmp_path)
    monkeypatch.setattr(
        browsers_command, "missing_browsers", lambda *_: ["chromium-1234"]
    )
    monkeypatch.setattr(browsers_command, "_launch_problem", lambda: None)
    monkeypatch.setattr(
        browsers_command.subprocess,
        "run",
        lambda command, env=None: subprocess.CompletedProcess(command, 0),
    )
    result = cli.invoke(harness_app, ["browsers"])
    assert result.exit_code == 1
    assert "incomplete" in result.stdout + result.stderr


def test_setup_uses_the_harness_installer():
    script = (browser_runtime.REPO_ROOT / "setup.sh").read_text(encoding="utf-8")
    assert "harness browsers" in script
    assert "playwright install" not in script
