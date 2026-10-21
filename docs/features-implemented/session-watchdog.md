# Potent Topaz session watchdog

`.devin/session_watchdog.py` checks `potent-topaz` immediately and every 30
minutes for at most 24 hours. When the session is released, it resumes the same
conversation through Devin CLI, preserving its saved model. It supplies no
`--model` flag and removes any inherited `DEVIN_MODEL` override.
No additional coordinator or agent session is created. This watchdog is a
Python scheduler; it does not currently run a separate DeepSeek supervisor.

## Commands

From the repository root, inspect without contacting the model:

```bash
.venv/bin/python .devin/session_watchdog.py check
```

Start a detached user service; this authorizes paid model requests when the
session becomes available:

```bash
systemd-run --user --unit=devin-watch-potent-topaz \
  --property=RuntimeMaxSec=24h --working-directory="$PWD" \
  "$PWD/.venv/bin/python" "$PWD/.devin/session_watchdog.py" run
```

The default uses Smart permissions. To explicitly authorize CLI bypass for
routine work, append `--permission-mode dangerous` to the command. Neither mode
authorizes the agent to ignore project restrictions or approve genuine human
decisions. Admin approval policies still apply.

```bash
journalctl --user -u devin-watch-potent-topaz -f
systemctl --user stop devin-watch-potent-topaz.service
```

Runtime files live in `.devin/afk-runtime/watch-potent-topaz/`. `worker.log`
contains CLI output. The persisted schedule prevents service restarts from
extending the deadline. A new run after expiry requires deliberately archiving
`schedule.json` and any previous `complete.json`, and starting the service again.

## Completion And Limits

The resumed agent is instructed to continue the approved plan without stopping
for progress-report acknowledgments. Only after the entire plan and its required
checks pass should it write `complete.json`, containing `session_id`, `summary`
and `verification`. The watchdog validates that report and exits; the user
service becomes inactive. Completion is agent-reported, not independently audited.
It also exits at the deadline, terminating its own outstanding CLI process group.

Desktop's live session lock is respected. There is no documented CLI command
to prompt an already-owned Desktop session, so a stopped or waiting conversation
that Desktop still owns is logged as `desktop-locked` and cannot be awakened.
Release the conversation in Desktop before relying on CLI continuation. The
watchdog never deletes locks, kills Desktop, or forks a competing coordinator.
An ambiguous lock or database error fails conservatively and is retried later.

The machine must remain awake with the user service manager running. The service
does not survive reboot or prevent suspension. Authentication, account model
availability, workspace trust and administrative approval requirements can block
continuation. No credentials or global CLI configuration are changed.

Offline tests cover expiry, live locks, dry runs, completion validation, the
session database/workspace check and model-preserving resume command. A paid CLI turn
and Desktop-to-CLI handoff require an explicitly approved live check. There is no
application UI change or screenshot requirement for this command.
