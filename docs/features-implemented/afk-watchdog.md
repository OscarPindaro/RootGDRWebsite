# Local AFK coordinator watchdog

Checks the Root GDR plan coordinator every thirty minutes and can resume work
through a separate local CLI worker, without stealing a live Desktop session.

## What it does

- The user timer runs at minute 00 and 30; its configured deadline is
  2026-10-05 10:00 Europe/Rome. Checks disable their own timer after the deadline
  or after the verified-completion marker is written.
- The watchdog reads only target-session metadata from Devin's local session
  database and verifies its PID lock. An open Desktop window is not treated as
  proof of active work: completed turns and tool activity are distinguished.
- Busy or ambiguous sessions are left alone. An idle locked Desktop gets a fresh
  CLI coordinator on the same plan; a closed session can be resumed. File locks
  and a single worker service prevent duplicate automatic workers.
- The worker uses Smart permissions and normal workspace trust. Its hook yields
  when Desktop resumes, and a bounded Stop hook discourages premature stopping.
  It never deletes session locks or kills existing Desktop processes.

## How it is built

Sources/configuration are under `.devin/`: `afk_watchdog.py`, the resume prompt,
standalone hooks and systemd user unit sources. Runtime state/logs and the
machine-local configuration are gitignored. Units are linked into systemd's
native user directory; no sudo or global Devin/Git configuration is changed.

The deadline and session/plan paths live in `.devin/afk-watchdog.local.json`.
The active desktop session is `flourish-random`. The watchdog's metadata reader
is version-specific and fails conservatively if that schema is unavailable.

```bash
systemctl --user status rootgdr-afk-watchdog.timer
systemctl --user status rootgdr-afk-worker.service
systemctl --user disable --now rootgdr-afk-watchdog.timer
uv run --frozen python .devin/afk_watchdog.py check --dry-run
```

## Limits

CLI authentication is separate from Desktop authentication. On setup the CLI
reported not logged in: `devin auth login` is required before automatic wake-up
can launch a worker. Detection/timer operation are tested; actual authenticated
wake-up must be verified after login. No credential values are read or logged.

Hooks are not assumed to hot-reload in an already-open Desktop process. They
apply reliably to newly launched CLI workers. Desktop resumption during an
already-running worker tool cannot preempt that tool safely; the worker yields
before its next tool. The PC must be awake and the user systemd manager running;
Persistent timers catch up after downtime but cannot wake a suspended computer.
