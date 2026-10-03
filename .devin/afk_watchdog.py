import argparse
import fcntl
import json
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / ".devin/afk-watchdog.local.json"


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository: Path
    plan: Path
    session_id: str
    deadline: datetime
    cli: Path
    model: str
    session_database: Path
    session_locks: Path
    runtime: Path
    prompt: Path
    enabled: bool = True
    idle_grace_seconds: int = Field(default=1800, ge=0)
    timer_unit: Literal["rootgdr-afk-watchdog.timer"] = "rootgdr-afk-watchdog.timer"


class SessionView(BaseModel):
    id: str
    working_directory: Path
    last_activity_at: int
    role: str | None = None
    finish_reason: str | None = None


class WorkerState(BaseModel):
    pid: int
    started_at: float
    original_leaf: int | None
    session_id: str | None = None


class HookEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")

    hook_event_name: str
    session_id: str
    stop_hook_active: bool = False


def load_settings(path: Path) -> Settings:
    settings = Settings.model_validate_json(path.read_text())
    if settings.deadline.tzinfo is None:
        raise ValueError("Watchdog deadline must include a timezone")
    if settings.repository.resolve() != ROOT:
        raise ValueError("Watchdog configuration belongs to a different repository")
    if not settings.plan.is_file() or not settings.prompt.is_file():
        raise ValueError("Watchdog plan/prompt file is unavailable")
    return settings


def atomic_state(path: Path, model: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(f".tmp-{os.getpid()}")
    with temporary.open("x") as output:
        os.chmod(temporary, 0o600)
        output.write(model.model_dump_json())
    temporary.replace(path)


def process_matches(pid: int, marker: str) -> bool:
    try:
        command = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ")
        return marker.encode() in command
    except FileNotFoundError, PermissionError, ProcessLookupError:
        return False


def lock_pid(settings: Settings, session_id: str) -> int | None:
    if not session_id or Path(session_id).name != session_id:
        raise ValueError("Invalid session identifier")
    path = settings.session_locks / f"{session_id}.lock"
    try:
        pid = int(path.read_text().strip())
    except FileNotFoundError, ValueError:
        return None
    return pid if process_matches(pid, "devin") else None


def session_view(
    settings: Settings, session_id: str
) -> tuple[SessionView | None, int | None]:
    connection = sqlite3.connect(
        f"{settings.session_database.as_uri()}?mode=ro", uri=True, timeout=5
    )
    try:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT s.id,s.working_directory,s.last_activity_at,s.main_chain_id,"
            "json_extract(n.chat_message,'$.role') AS role,"
            "json_extract(n.chat_message,'$.metadata.finish_reason') AS finish_reason "
            "FROM sessions s LEFT JOIN message_nodes n "
            "ON n.session_id=s.id AND n.node_id=s.main_chain_id WHERE s.id=?",
            (session_id,),
        ).fetchone()
        if row is None:
            return None, None
        return SessionView.model_validate(dict(row)), row["main_chain_id"]
    finally:
        connection.close()


def phase(
    view: SessionView, live_pid: int | None, now: float, grace: int
) -> Literal["busy", "idle", "closed", "unknown"]:
    if live_pid is None:
        return "closed"
    if view.finish_reason == "stop" and now - view.last_activity_at >= grace:
        return "idle"
    if view.role in {"user", "tool"} or view.finish_reason == "tool_calls":
        return "busy"
    if now - view.last_activity_at < grace:
        return "busy"
    return "unknown"


def worker_state(settings: Settings) -> WorkerState | None:
    path = settings.runtime / "worker.json"
    try:
        state = WorkerState.model_validate_json(path.read_text())
    except FileNotFoundError:
        return None
    return state if process_matches(state.pid, str(Path(__file__).resolve())) else None


def finished(settings: Settings, now: datetime) -> bool:
    return (
        not settings.enabled
        or now >= settings.deadline
        or (settings.runtime / "complete").exists()
    )


def report(settings: Settings, action: str) -> None:
    settings.runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (settings.runtime / "watchdog.log").open("a") as log:
        log.write(f"{datetime.now(timezone.utc).isoformat()} {action}\n")
    print(action)


def authenticated(settings: Settings) -> bool:
    result = subprocess.run(
        [str(settings.cli), "auth", "status"],
        cwd=settings.repository,
        capture_output=True,
        text=True,
        timeout=30,
    )
    text = result.stdout.casefold()
    return (
        result.returncode == 0
        and "not logged in" not in text
        and ("logged in" in text or "authenticated" in text)
    )


def check(settings: Settings, config: Path, *, dry_run: bool = False) -> str:
    now = datetime.now(timezone.utc)
    if finished(settings, now):
        report(settings, "expired-or-complete")
        if not dry_run:
            subprocess.run(
                ["systemctl", "--user", "disable", "--now", settings.timer_unit],
                capture_output=True,
                text=True,
                timeout=30,
            )
        return "expired-or-complete"
    if worker_state(settings) is not None:
        report(settings, "worker-active")
        return "worker-active"
    view, _ = session_view(settings, settings.session_id)
    if (
        view is None
        or view.working_directory.resolve() != settings.repository.resolve()
    ):
        report(settings, "session-unavailable-or-wrong-workspace")
        return "session-unavailable-or-wrong-workspace"
    state = phase(
        view,
        lock_pid(settings, settings.session_id),
        now.timestamp(),
        settings.idle_grace_seconds,
    )
    if state in {"busy", "unknown"}:
        report(settings, f"desktop-{state}")
        return f"desktop-{state}"
    if (settings.runtime / "blocked").exists():
        report(settings, "operator-blocker")
        return "operator-blocker"
    if dry_run:
        report(settings, f"would-wake-{state}")
        return f"would-wake-{state}"
    if not authenticated(settings):
        report(settings, "authentication-required: run devin auth login")
        return "authentication-required"
    log_path = settings.runtime / "worker.log"
    log_path.touch(mode=0o600, exist_ok=True)
    launched = subprocess.run(
        ["systemctl", "--user", "start", "--no-block", "rootgdr-afk-worker.service"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    action = (
        "worker-launched"
        if launched.returncode == 0
        else "worker-launch-failed-or-already-active"
    )
    report(settings, action)
    return action


def run_worker(settings: Settings) -> int:
    lock_path = settings.runtime / "worker.lock"
    settings.runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
    with lock_path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        if finished(settings, datetime.now(timezone.utc)):
            return 0
        view, leaf = session_view(settings, settings.session_id)
        if view is None:
            return 1
        status = phase(
            view,
            lock_pid(settings, settings.session_id),
            time.time(),
            settings.idle_grace_seconds,
        )
        if status not in {"closed", "idle"}:
            return 0
        previous_path = settings.runtime / "worker.json"
        previous = (
            WorkerState.model_validate_json(previous_path.read_text())
            if previous_path.exists()
            else None
        )
        resume_id = (
            settings.session_id
            if status == "closed"
            else (previous.session_id if previous is not None else None)
        )
        if resume_id is not None and lock_pid(settings, resume_id) is not None:
            return 0
        atomic_state(
            settings.runtime / "worker.json",
            WorkerState(
                pid=os.getpid(),
                started_at=time.time(),
                original_leaf=leaf,
                session_id=resume_id,
            ),
        )
        command = [
            str(settings.cli),
            "--permission-mode",
            "smart",
            "--model",
            settings.model,
            "--prompt-file",
            str(settings.prompt),
            "--print",
        ]
        if resume_id is not None:
            command.extend(["--resume", resume_id])
        environment = os.environ.copy()
        environment["ROOTGDR_AFK_WORKER"] = "1"
        environment["ROOTGDR_AFK_SUPERVISOR_PID"] = str(os.getpid())
        report(settings, f"working-on-plan: {settings.plan.name}")
        result = subprocess.run(command, cwd=settings.repository, env=environment)
        report(settings, f"worker-exit-{result.returncode}")
        return result.returncode


def hook(settings: Settings, event: HookEvent) -> None:
    is_worker = os.environ.get("ROOTGDR_AFK_WORKER") == "1"
    if event.session_id != settings.session_id and not is_worker:
        return
    if is_worker:
        state = worker_state(settings)
        if state is not None and state.session_id != event.session_id:
            state.session_id = event.session_id
            atomic_state(settings.runtime / "worker.json", state)
        original, leaf = session_view(settings, settings.session_id)
        desktop_resumed = (
            event.session_id != settings.session_id
            and state is not None
            and leaf != state.original_leaf
            and original is not None
            and (
                phase(original, lock_pid(settings, settings.session_id), time.time(), 0)
                == "busy"
            )
        )
        if desktop_resumed:
            if event.hook_event_name == "PreToolUse":
                print(
                    json.dumps(
                        {
                            "decision": "block",
                            "reason": "Desktop coordinator resumed. Stop this AFK worker without writing; do not run a second coordinator.",
                        }
                    )
                )
            return
    if event.hook_event_name == "Stop" and not finished(
        settings, datetime.now(timezone.utc)
    ):
        if not event.stop_hook_active and not (settings.runtime / "blocked").exists():
            print(
                json.dumps(
                    {
                        "decision": "block",
                        "reason": "The approved AFK plan is unfinished. Continue the next ticket, delegate isolated work, verify and commit. Stop only for a genuine operator blocker or after the configured deadline.",
                    }
                )
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["check", "worker", "hook"])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    settings = load_settings(args.config)
    if args.action == "hook":
        hook(settings, HookEvent.model_validate_json(sys.stdin.read()))
        return 0
    if args.action == "worker":
        return run_worker(settings)
    settings.runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (settings.runtime / "check.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        check(settings, args.config, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
