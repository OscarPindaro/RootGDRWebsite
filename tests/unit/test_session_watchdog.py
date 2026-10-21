import importlib.util
import json
import sqlite3
import sys
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / ".devin/session_watchdog.py"
SPEC = importlib.util.spec_from_file_location("session_watchdog", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
watchdog = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = watchdog
SPEC.loader.exec_module(watchdog)


@pytest.fixture
def schedule(tmp_path, monkeypatch):
    monkeypatch.setattr(watchdog, "RUNTIME", tmp_path)
    monkeypatch.setattr(watchdog, "session", lambda: None)
    return watchdog.Schedule(
        started_at=time.time(), deadline=time.time() + 3600, permission_mode="smart"
    )


def test_expiry_does_not_read_session_or_launch(schedule, monkeypatch):
    schedule.deadline = 0
    monkeypatch.setattr(watchdog, "session", lambda: pytest.fail("session accessed"))
    assert watchdog.check(schedule) == "expired"


def test_live_desktop_never_launches_competing_worker(schedule, monkeypatch):
    monkeypatch.setattr(watchdog, "locked", lambda: True)
    monkeypatch.setattr(
        watchdog.subprocess, "Popen", lambda *a, **k: pytest.fail("launch")
    )
    assert watchdog.check(schedule).startswith("desktop-locked")


def test_dry_run_never_launches(schedule, monkeypatch):
    monkeypatch.setattr(watchdog, "locked", lambda: False)
    monkeypatch.setattr(
        watchdog.subprocess, "Popen", lambda *a, **k: pytest.fail("launch")
    )
    assert watchdog.check(schedule, dry_run=True) == "would-resume"


def test_completion_requires_scoped_verification(schedule, monkeypatch):
    monkeypatch.setattr(watchdog, "locked", lambda: False)
    marker = watchdog.RUNTIME / "complete.json"
    marker.write_text(
        json.dumps(
            {
                "session_id": "potent-topaz",
                "summary": "All approved plan tickets completed.",
                "verification": "Integration tests and visual checks passed.",
            }
        )
    )
    assert watchdog.check(schedule) == "complete"
    marker.write_text('{"session_id": "another-session"}')
    with pytest.raises(ValueError):
        watchdog.check(schedule)


def test_locked_desktop_does_not_read_partial_report(schedule, monkeypatch):
    monkeypatch.setattr(watchdog, "locked", lambda: True)
    (watchdog.RUNTIME / "complete.json").write_text("{")
    assert watchdog.check(schedule).startswith("desktop-locked")


def test_reads_real_session_database_and_rejects_wrong_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(watchdog, "DATA", tmp_path)
    with sqlite3.connect(tmp_path / "sessions.db") as connection:
        connection.execute(
            "CREATE TABLE sessions(id TEXT, working_directory TEXT, model TEXT, "
            "last_activity_at INTEGER)"
        )
        connection.execute(
            "INSERT INTO sessions VALUES(?,?,?,?)",
            (watchdog.SESSION, str(watchdog.ROOT), watchdog.MODEL, 1),
        )
    assert watchdog.session().model == watchdog.MODEL
    with sqlite3.connect(tmp_path / "sessions.db") as connection:
        connection.execute("UPDATE sessions SET working_directory='/another-workspace'")
    with pytest.raises(ValueError, match="another workspace"):
        watchdog.session()


def test_stale_and_ambiguous_locks(tmp_path, monkeypatch):
    monkeypatch.setattr(watchdog, "DATA", tmp_path)
    locks = tmp_path / "session_locks"
    locks.mkdir()
    lock = locks / f"{watchdog.SESSION}.lock"
    assert not watchdog.locked()
    lock.write_text("invalid")
    assert watchdog.locked()
    lock.write_text("999999999")
    assert not watchdog.locked()


def test_resume_command_is_pinned_and_keeps_session_identity(schedule, monkeypatch):
    monkeypatch.setattr(watchdog, "locked", lambda: False)
    monkeypatch.setattr(watchdog.shutil, "which", lambda name: "/bin/devin")
    monkeypatch.setenv("ACP_BACKEND", "desktop")
    monkeypatch.setattr(
        watchdog,
        "session",
        lambda: watchdog.Session(
            id=watchdog.SESSION,
            working_directory=watchdog.ROOT,
            model=watchdog.MODEL,
            last_activity_at=1,
        ),
    )

    class Process:
        def __init__(self, command, **kwargs):
            assert command[:5] == [
                "/bin/devin",
                "--resume",
                "potent-topaz",
                "--model",
                watchdog.MODEL,
            ]
            assert command[5:7] == ["--permission-mode", "smart"]
            assert "ACP_BACKEND" not in kwargs["env"]
            assert kwargs["stdin"] == watchdog.subprocess.DEVNULL

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def wait(self, timeout):
            assert 0 < timeout <= 3600
            return 0

    monkeypatch.setattr(watchdog.subprocess, "Popen", Process)
    assert watchdog.check(schedule) == "turn-ended: will check again"
