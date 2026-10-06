"""The CI artifact collector (REQ-0001/T02).

Failure-only diagnostics: the allowlisted files of failed runs, redacted and
size-capped, never the whole artifacts directory and never an environment file.
"""

from __future__ import annotations

import json
from pathlib import Path

from tools.ci.collect_artifacts import TOTAL_LIMIT, collect, redact


def _run(root: Path, name: str, status: str, files: dict[str, str]) -> Path:
    run = root / name
    (run / "screenshots").mkdir(parents=True, exist_ok=True)
    (run / "manifest.json").write_text(
        json.dumps({"id": name, "status": status}), encoding="utf-8"
    )
    for filename, content in files.items():
        target = run / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return run


def test_only_failed_runs_are_collected(tmp_path: Path) -> None:
    root = tmp_path / "harness-artifacts"
    _run(root, "20260101-000000-aaaa", "failed", {"logs/run.log": "boom\n"})
    _run(root, "20260101-000000-bbbb", "passed", {"logs/run.log": "fine\n"})

    collection = collect(root, tmp_path / "out")

    assert collection.runs == ["20260101-000000-aaaa"]
    assert [row.destination for row in collection.files] == [
        "20260101-000000-aaaa/logs/run.log"
    ]
    assert not (tmp_path / "out" / "20260101-000000-bbbb").exists()


def test_the_allowlist_and_the_redaction_apply(tmp_path: Path) -> None:
    root = tmp_path / "harness-artifacts"
    _run(
        root,
        "20260101-000000-aaaa",
        "failed",
        {
            "logs/run.log": "AUTH__JWT_SECRET=supersecretvalue\nheader: Bearer abc.def\n",
            "compare/report.html": "<html>report</html>",
            ".env": "DATABASE_PASSWORD=leak\n",
            "screenshots/desktop.png": "not-really-a-png",
        },
    )

    collection = collect(root, tmp_path / "out")

    names = sorted(row.destination for row in collection.files)
    assert names == [
        "20260101-000000-aaaa/logs/run.log",
        "20260101-000000-aaaa/screenshots/desktop.png",
    ]
    log = (tmp_path / "out" / "20260101-000000-aaaa" / "logs" / "run.log").read_text()
    assert "supersecretvalue" not in log
    assert "abc.def" not in log
    assert "[redacted]" in log
    assert not (tmp_path / "out" / "20260101-000000-aaaa" / ".env").exists()
    assert not (tmp_path / "out" / "20260101-000000-aaaa" / "compare").exists()


def test_an_oversized_file_is_skipped(tmp_path: Path) -> None:
    root = tmp_path / "harness-artifacts"
    _run(
        root,
        "20260101-000000-aaaa",
        "failed",
        {"logs/big.log": "x" * (TOTAL_LIMIT + 1), "logs/small.log": "ok\n"},
    )

    collection = collect(root, tmp_path / "out")

    assert [row.destination for row in collection.files] == [
        "20260101-000000-aaaa/logs/small.log"
    ]
    assert collection.skipped == ["20260101-000000-aaaa/logs/big.log"]
    assert collection.total_bytes <= TOTAL_LIMIT


def test_redaction_leaves_ordinary_text_alone() -> None:
    text = "FAILED tests/unit/test_config.py::test_alpha\nAssertionError: 1 != 2\n"

    cleaned, changed = redact(text)

    assert cleaned == text
    assert changed is False
