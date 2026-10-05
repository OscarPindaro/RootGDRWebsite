"""Release-notes tooling and version authority (REQ-0012/T06)."""

import hashlib
import importlib.metadata
import json
import subprocess
import sys
import tomllib
from pathlib import Path

from harness.backlog.requests import REPO_ROOT

CHANGELOG = REPO_ROOT / "CHANGELOG.md"
FRAGMENTS = REPO_ROOT / "changelog.d"


def run_draft(
    directory: Path, version: str = "UNRELEASED"
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "towncrier",
            "build",
            "--draft",
            "--version",
            version,
            "--config",
            str(REPO_ROOT / "pyproject.toml"),
            "--dir",
            str(directory),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )


def checksums() -> dict[Path, str]:
    paths = [CHANGELOG, *sorted(FRAGMENTS.glob("*.md"))]
    return {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def test_pyproject_is_the_only_version_authority():
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text("utf-8"))[
        "project"
    ]
    assert project["version"] == "0.1.0"
    package = json.loads((REPO_ROOT / "package.json").read_text("utf-8"))
    assert "version" not in package
    assert importlib.metadata.version("backend") == project["version"]


def test_draft_leaves_fragments_changelog_and_version_untouched():
    before = checksums()
    result = run_draft(REPO_ROOT)
    assert result.returncode == 0, result.stderr
    assert "Draft only -- nothing has been written." in result.stdout + result.stderr
    assert "### Added" in result.stdout
    assert "(REQ-0012-T05)" in result.stdout
    assert checksums() == before


def test_invalid_fragment_name_is_rejected(tmp_path):
    (tmp_path / "changelog.d").mkdir()
    (tmp_path / "changelog.d" / "notes.txt").write_text("bad\n", encoding="utf-8")
    result = run_draft(tmp_path)
    assert result.returncode != 0
    assert "notes.txt" in result.stdout + result.stderr


def test_fragments_aggregate_by_type(tmp_path):
    (tmp_path / "changelog.d").mkdir()
    (tmp_path / "changelog.d" / "REQ-9999-T01.fixed.md").write_text(
        "A fixture note.\n", encoding="utf-8"
    )
    result = run_draft(tmp_path, version="9.9.9")
    assert result.returncode == 0, result.stderr
    assert "## 9.9.9" in result.stdout
    assert "### Fixed" in result.stdout
    assert "A fixture note." in result.stdout
    assert "(REQ-9999-T01)" in result.stdout
