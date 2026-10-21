"""Resume a released Devin session periodically, without taking over Desktop."""

import argparse
import fcntl
import json
import os
import shutil
import signal
import sqlite3
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
DATA = Path.home() / ".local/share/devin/cli"
MODEL = "deepseek-v4-1-flash-1017-high"
SESSION = "potent-topaz"
RUNTIME = ROOT / ".devin/afk-runtime" / f"watch-{SESSION}"


class Session(BaseModel):
    id: str
    working_directory: Path
    model: str
    last_activity_at: int


class Completion(BaseModel):
    session_id: Literal["potent-topaz"]
    summary: str = Field(min_length=20)
    verification: str = Field(min_length=20)


class Schedule(BaseModel):
    started_at: float
    deadline: float
    permission_mode: Literal["smart", "dangerous"]


def session() -> Session:
    with sqlite3.connect(
        f"{(DATA / 'sessions.db').as_uri()}?mode=ro", uri=True, timeout=5
    ) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT id, working_directory, model, last_activity_at "
            "FROM sessions WHERE id = ?",
            (SESSION,),
        ).fetchone()
    if row is None:
        raise ValueError(f"Session {SESSION} does not exist")
    result = Session.model_validate(dict(row))
    if result.working_directory.resolve() != ROOT:
        raise ValueError("Session belongs to another workspace")
    return result


def locked() -> bool:
    path = DATA / "session_locks" / f"{SESSION}.lock"
    if not path.exists():
        return False
    try:
        pid = int(path.read_text().strip())
        executable = Path(f"/proc/{pid}/exe").resolve(strict=True)
        command = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
        return executable.name == "devin" and bool(command)
    except ValueError, PermissionError:
        # Ambiguous locks must not permit a second coordinator.
        return True
    except FileNotFoundError, ProcessLookupError:
        return False


def completed() -> bool:
    path = RUNTIME / "complete.json"
    if not path.exists():
        return False
    Completion.model_validate_json(path.read_text())
    return True


def log(message: str) -> None:
    print(f"{datetime.now(UTC).isoformat()} {message}", flush=True)


def check(schedule: Schedule, *, dry_run: bool = False) -> str:
    if time.time() >= schedule.deadline:
        return "expired"
    session()
    # Desktop may still be finishing its turn; never inspect a half-written
    # completion report or launch another coordinator while its lock is live.
    if locked():
        return "desktop-locked: cannot prompt this live session through CLI"
    if completed():
        return "complete"
    if dry_run:
        return "would-resume"
    cli = shutil.which("devin")
    if cli is None:
        raise ValueError("devin executable is not on PATH")
    prompt = RUNTIME / "prompt.md"
    prompt.write_text(
        f"""Continue the existing approved plan in session {SESSION}.
Read its latest instructions and durable coordinator/worker state first.
Do not start a new plan or a competing coordinator. Verify worker identity,
boot ID and fresh results before treating saved running states as live.
Continue the next unfinished step; do not stop for a routine progress report
or ask whether to continue. Use reasonable decisions within the approved scope.
Preserve existing restrictions, user changes, test environments and credentials.
Do not approve destructive actions, deployments, pushes, additional delegation,
or external writes that lack explicit user authorization. Record genuine human
blockers clearly and stop that turn rather than inventing approval.

Only when the ENTIRE approved plan and its required verification are finished,
write {RUNTIME / "complete.json"} as JSON with exactly these fields:
session_id: "{SESSION}", summary: factual completed outcome,
verification: concrete passing checks and evidence.
Do not write it for a partial ticket, a blocker or a handoff. This report ends
the watchdog. You are using pinned {MODEL}; do not switch models.
The watchdog deadline is {datetime.fromtimestamp(schedule.deadline, UTC).isoformat()}.
"""
    )
    command = [
        cli,
        "--resume",
        SESSION,
        "--model",
        MODEL,
        "--permission-mode",
        schedule.permission_mode,
        "--prompt-file",
        str(prompt),
        "--print",
    ]
    environment = os.environ.copy()
    environment.pop("ACP_BACKEND", None)
    environment["DEVIN_MODEL"] = MODEL
    environment["DEVIN_PERMISSION_MODE"] = schedule.permission_mode
    with (RUNTIME / "worker.log").open("a") as output:
        with subprocess.Popen(
            command,
            cwd=ROOT,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        ) as process:
            try:
                code = process.wait(timeout=max(1, schedule.deadline - time.time()))
            except BaseException:
                # Only terminate the process group created by this invocation.
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                raise
    if code:
        return f"resume-failed-{code}: see {RUNTIME / 'worker.log'}"
    if session().model != MODEL:
        raise ValueError("Resumed session did not retain the requested model")
    return "complete" if completed() else "turn-ended: will check again"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["run", "check"])
    parser.add_argument("--hours", type=float, default=24)
    parser.add_argument("--interval", type=float, default=1800)
    parser.add_argument(
        "--permission-mode", choices=["smart", "dangerous"], default="smart"
    )
    args = parser.parse_args()
    if not 0 < args.hours <= 24 or args.interval < 1:
        parser.error("hours must be in (0, 24]; interval must be at least 1 second")
    RUNTIME.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.umask(0o077)
    with (RUNTIME / "watchdog.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log("another watchdog is already running")
            return 1
        schedule = Schedule(
            started_at=time.time(),
            deadline=time.time() + args.hours * 3600,
            permission_mode=args.permission_mode,
        )
        if args.action == "check":
            log(check(schedule, dry_run=True))
            return 0
        path = RUNTIME / "schedule.json"
        if path.exists():
            schedule = Schedule.model_validate_json(path.read_text())
        else:
            path.write_text(schedule.model_dump_json(indent=2) + "\n")
        log(f"watching {SESSION}; deadline={schedule.deadline}; model={MODEL}")
        while True:
            started = time.monotonic()
            try:
                result = check(schedule)
            except (
                OSError,
                ValueError,
                sqlite3.Error,
                subprocess.TimeoutExpired,
            ) as error:
                result = f"check-failed: {error}"
            log(result)
            if result in {"complete", "expired"}:
                return 0
            remaining = schedule.deadline - time.time()
            if remaining <= 0:
                return 0
            time.sleep(
                min(remaining, max(0, args.interval - (time.monotonic() - started)))
            )


if __name__ == "__main__":
    raise SystemExit(main())
