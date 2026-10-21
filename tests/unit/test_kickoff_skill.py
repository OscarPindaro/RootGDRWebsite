"""Exercise kickoff discovery on disposable directories without scaffolding."""

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SCRIPT = (
    Path(__file__).resolve().parents[2] / ".devin/skills/kickoff/scripts/detect-mode.sh"
)


@pytest.mark.parametrize(
    ("kind", "expected", "status"),
    (
        ("missing", "missing", 0),
        ("empty", "empty", 0),
        ("docs", "empty", 0),
        ("manifest", "existing", 0),
        ("worktree", "existing", 0),
        ("source", "existing", 0),
        ("legacy", "kickoff", 0),
        ("data", "nonproject", 0),
        ("private", "nonproject", 0),
        ("file", "", 2),
        ("symlink", "", 2),
    ),
)
def test_kickoff_detects_without_changing_files(
    tmp_path: Path, kind: str, expected: str, status: int
) -> None:
    assert SCRIPT.is_file()
    target = tmp_path / "project with spaces"
    if kind == "file":
        target.write_text("preserve")
    elif kind == "symlink":
        destination = tmp_path / "destination"
        destination.mkdir()
        target.symlink_to(destination, target_is_directory=True)
    elif kind != "missing":
        target.mkdir()
        if kind == "docs":
            (target / "README.md").write_text("Project")
            (target / ".gitignore").write_text(".venv/")
        elif kind == "manifest":
            (target / "pyproject.toml").write_text("[project]")
        elif kind == "worktree":
            (target / ".git").write_text("gitdir: /not-used")
        elif kind == "source":
            (target / "src" / "backend").mkdir(parents=True)
        elif kind == "legacy":
            (target / ".kickoff-project").write_text("existing marker")
        elif kind == "data":
            (target / "notes.txt").write_text("preserve")
        elif kind == "private":
            (target / ".env").write_text("preserve")
    before_paths = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    before = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    result = subprocess.run(
        ["bash", str(SCRIPT), str(target)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == status, result.stderr
    assert result.stdout.strip() == expected
    assert before_paths == sorted(
        path.relative_to(tmp_path) for path in tmp_path.rglob("*")
    )
    assert before == {
        path.relative_to(tmp_path): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
