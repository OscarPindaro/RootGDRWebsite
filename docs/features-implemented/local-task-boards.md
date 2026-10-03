# Local task-board trials

Kanboard and Vikunja run beside Root GDR without sharing the application's
database or test-harness state. After the local comparison, the user selected
**Vikunja** as the ticket board. Kanboard is retained only for comparison; its
data has not been removed.

## What it does

- Vikunja 2.6.0: http://localhost:3456 — create your own account in the UI.
- Kanboard 1.2.54: http://localhost:3457 — the upstream initial login is
  `admin` / `admin`. Change the password immediately after signing in.
- Both ports bind to `127.0.0.1` only. This is not an Internet deployment.
- Each board uses its own SQLite database and persistent named volumes.
- Vikunja's signing secret is generated once inside its database volume, with
  restricted permissions; it is not stored in Git or printed during setup.
- Vikunja mail delivery and public link sharing are off. Kanboard's plugin
  installer is off. Vikunja self-registration stays on for the local trial.

## Demonstration data

Both boards contain `Root GDR — prova board`, with ten example tickets:
4 in Backlog, 2 In corso, 2 in Review and 2 in Conclusi. The cards include
categories, priorities, acceptance checklists, and blocked/deferred examples.
Kanboard also has native subtasks; Vikunja has comments and sample due dates.
All progress is explicitly simulated, not a statement about real project work.

- Vikunja: http://localhost:3456/projects/4/26 — the `Prova workflow` view.
  The demonstration project is shared with the existing `admin` account.
  A separate `rootgdr-demo` account owns it; no existing password was changed.
- Kanboard: http://localhost:3457/?controller=BoardViewController&action=show&project_id=1

The initial, incomplete Vikunja import was archived as
`Root GDR — importazione demo tecnica (archiviata)`, without deleting data.
The visible comparison project was verified to have ten unique cards through
both the API and the browser; rerunning the temporary seed did not duplicate it.
No real backlog was imported, and no generic ticket harness exists yet.

## How it is built

`deploy/task-boards.compose.yaml` is a standalone Compose project named
`rootgdr-task-boards`. It does not load Root GDR's `.env` or join its network.
Images are pinned rather than following `latest`.

Vikunja's upstream image runs as UID 1000 and has no shell. A setup-only
BusyBox service prepares ownership and the signing secret on its volumes. It
is not a runtime dependency, so restarting Vikunja works under Podman too.
Setup is idempotent: it does not replace an existing secret or reset a database.

From the repository root, with Podman Compose:

```bash
podman-compose -f deploy/task-boards.compose.yaml --profile setup run --rm vikunja-init
podman-compose -f deploy/task-boards.compose.yaml up -d
podman-compose -f deploy/task-boards.compose.yaml ps
podman-compose -f deploy/task-boards.compose.yaml logs --tail=40
podman-compose -f deploy/task-boards.compose.yaml restart vikunja kanboard
podman-compose -f deploy/task-boards.compose.yaml stop
```

Docker Compose can use the same file and commands with `docker compose` in
place of `podman-compose`. Only the Podman deployment was exercised here.
Run setup before first startup, or after restoring volumes to a new host.
`up -d` starts only the two boards because initialization is in the setup profile.

Data lives in `rootgdr-task-boards_vikunja-db`,
`rootgdr-task-boards_vikunja-files`, and `rootgdr-task-boards_kanboard-data`.
Stopping or restarting does not delete them. Do not use `down --volumes` or
remove these volumes without explicit approval. Back up both databases and
uploaded files before any migration; SQLite backups must be consistent.

Readiness checks:

```bash
curl --fail http://localhost:3456/api/v1/info
curl --fail http://localhost:3457/healthcheck.php
```

`tests/unit/test_task_boards_deployment.py` checks image pins, loopback bindings,
storage separation, secret location, and trial settings. Browser checks covered
both login screens at 1440×900 and 390×844, plus Kanboard login, without browser
errors or horizontal overflow. Both services were checked after a restart.

## Limits

- Vikunja is the chosen authority for state and backlog, but no real backlog has
  been imported and no ticket API integration is built yet. The demo project is
  not the real backlog. Future ticket tooling should target Vikunja only.
- The repository remains the authority for specifications, feature manuals and
  release notes. Do not maintain current ticket state manually in both places.
- Kanboard's documentation includes a SQLite Compose example but elsewhere
  discourages SQLite with Docker/NFS. This local trial follows the example;
  production database/storage support must be reviewed before server deployment.
- There is no TLS, off-host access, mail setup, automated backup or production
  hardening. Loopback binding is not a replacement for authentication; other
  users and software on the same machine may still reach these ports.
- This Compose project has fixed ports and volume names, not per-worktree
  isolation. It is separate from `harness env` and must not be reset by tests.
