import importlib.util
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / ".devin/afk_watchdog.py"
SPEC = importlib.util.spec_from_file_location("rootgdr_afk_watchdog", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
watchdog = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = watchdog
SPEC.loader.exec_module(watchdog)


@pytest.fixture
def settings(tmp_path: Path):
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Continue the approved plan")
    plan = tmp_path / "plan.md"
    plan.write_text("Approved plan")
    database = tmp_path / "sessions.db"
    connection = sqlite3.connect(database)
    connection.executescript(
        "CREATE TABLE sessions(id TEXT,working_directory TEXT,last_activity_at INTEGER,main_chain_id INTEGER);"
        "CREATE TABLE message_nodes(session_id TEXT,node_id INTEGER,chat_message TEXT);"
    )
    message = json.dumps({"role": "assistant", "metadata": {"finish_reason": "stop"}})
    with connection:
        connection.execute(
            "INSERT INTO sessions VALUES(?,?,?,?)", ("target", str(watchdog.ROOT), 1, 8)
        )
        connection.execute(
            "INSERT INTO message_nodes VALUES(?,?,?)", ("target", 8, message)
        )
    connection.close()
    return watchdog.Settings(
        repository=watchdog.ROOT,
        plan=plan,
        prompt=prompt,
        session_id="target",
        deadline=datetime.now(timezone.utc) + timedelta(days=1),
        cli=Path("/not-a-cli"),
        model="test-model",
        session_database=database,
        session_locks=tmp_path / "locks",
        runtime=tmp_path / "runtime",
    )


@pytest.mark.parametrize(
    "role,finish,pid,activity,expected",
    [
        ("tool", None, 123, 1, "busy"),
        ("assistant", "tool_calls", 123, 1, "busy"),
        ("assistant", "stop", 123, 1, "idle"),
        ("assistant", None, 123, 1, "unknown"),
        ("assistant", "stop", None, 1, "closed"),
        ("assistant", "stop", 123, 1900, "busy"),
    ],
)
def test_phase_does_not_confuse_open_desktop_with_active_work(
    role, finish, pid, activity, expected
):
    view = watchdog.SessionView(
        id="target",
        working_directory=watchdog.ROOT,
        last_activity_at=activity,
        role=role,
        finish_reason=finish,
    )
    assert watchdog.phase(view, pid, 2000, 1800) == expected


def test_reads_only_target_main_chain_metadata(settings):
    view, leaf = watchdog.session_view(settings, "target")
    assert view.id == "target"
    assert view.finish_reason == "stop"
    assert leaf == 8
    assert watchdog.session_view(settings, "unrelated") == (None, None)


def test_dry_run_does_not_start_an_agent(settings, monkeypatch):
    monkeypatch.setattr(watchdog, "lock_pid", lambda *args: None)
    assert watchdog.check(settings, Path("unused"), dry_run=True) == "would-wake-closed"
    assert not (settings.runtime / "worker.json").exists()


def test_busy_session_skips_authentication_and_launch(settings, monkeypatch):
    monkeypatch.setattr(watchdog, "lock_pid", lambda *args: 123)
    monkeypatch.setattr(watchdog, "phase", lambda *args: "busy")
    assert watchdog.check(settings, Path("unused")) == "desktop-busy"


def test_missing_cli_auth_is_a_real_blocker(settings, monkeypatch):
    monkeypatch.setattr(watchdog, "lock_pid", lambda *args: None)
    monkeypatch.setattr(watchdog, "authenticated", lambda *args: False)
    assert watchdog.check(settings, Path("unused")) == "authentication-required"


def test_deadline_and_completion_stop_wakes(settings):
    now = datetime.now(timezone.utc)
    assert not watchdog.finished(settings, now)
    assert watchdog.finished(settings, settings.deadline)
    settings.runtime.mkdir()
    (settings.runtime / "complete").write_text("verified")
    assert watchdog.finished(settings, now)


def test_stop_guard_is_scoped_and_does_not_loop(settings, capsys):
    unrelated = watchdog.HookEvent(hook_event_name="Stop", session_id="unrelated")
    watchdog.hook(settings, unrelated)
    assert capsys.readouterr().out == ""
    target = watchdog.HookEvent(hook_event_name="Stop", session_id="target")
    watchdog.hook(settings, target)
    assert json.loads(capsys.readouterr().out)["decision"] == "block"
    target.stop_hook_active = True
    watchdog.hook(settings, target)
    assert capsys.readouterr().out == ""


def test_guard_rejects_session_identifier_path_traversal(settings):
    with pytest.raises(ValueError, match="identifier"):
        watchdog.lock_pid(settings, "../other-session")


def test_worker_yields_when_desktop_resumes(settings, monkeypatch, capsys):
    monkeypatch.setenv("ROOTGDR_AFK_WORKER", "1")
    monkeypatch.setattr(watchdog, "process_matches", lambda *args: True)
    monkeypatch.setattr(watchdog, "lock_pid", lambda *args: 123)
    watchdog.atomic_state(
        settings.runtime / "worker.json",
        watchdog.WorkerState(
            pid=123,
            started_at=1,
            original_leaf=7,
        ),
    )
    monkeypatch.setattr(watchdog, "phase", lambda *args: "busy")
    event = watchdog.HookEvent(hook_event_name="PreToolUse", session_id="worker-child")
    watchdog.hook(settings, event)
    assert json.loads(capsys.readouterr().out)["decision"] == "block"
    event.hook_event_name = "Stop"
    watchdog.hook(settings, event)
    assert capsys.readouterr().out == ""


def test_resuming_original_session_does_not_block_its_own_worker(
    settings, monkeypatch, capsys
):
    monkeypatch.setenv("ROOTGDR_AFK_WORKER", "1")
    monkeypatch.setattr(watchdog, "process_matches", lambda *args: True)
    monkeypatch.setattr(watchdog, "lock_pid", lambda *args: 123)
    monkeypatch.setattr(watchdog, "phase", lambda *args: "busy")
    watchdog.atomic_state(
        settings.runtime / "worker.json",
        watchdog.WorkerState(
            pid=123,
            started_at=1,
            original_leaf=7,
        ),
    )
    event = watchdog.HookEvent(hook_event_name="PreToolUse", session_id="target")
    watchdog.hook(settings, event)
    assert capsys.readouterr().out == ""
