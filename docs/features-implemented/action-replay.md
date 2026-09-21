# Record what you do and generate a test

A bug found by hand should become a test that reproduces it, without writing the
test by hand — and a recording taken where the bug happened should replay
somewhere else.

## What it does

Two recordings:

- **Browser steps.** Switch on *Registra azioni* in the user menu and work
  normally. Each page, field and click is recorded as a semantic step ("filled
  `name` with X", "clicked the link to `/worlds/new`").
  `harness replay export <session>` writes a Playwright test.
- **Backend calls.** `harness replay start`, work (even with curl), then
  `harness replay stop`. Every request is recorded with its response status
  *and response body* (size-capped), and `harness replay export <session>
  --mode backend` writes an integration test that replays them and asserts the
  statuses. Start with `--read-only` to keep only GET, HEAD and OPTIONS, and
  repeat `--exclude /path` to omit path prefixes.

`harness replay list` and `show <session> [--mode ui|backend]` inspect a
recording. `harness replay diff <before> <after>` reports added, removed and
changed steps with volatile values normalized.

### What the replay asserts

Every step asserts the recorded status. Where the recorded response was a JSON
object (the API's single-resource bodies), the generated test also compares the
body: UUIDs and complete ISO timestamps are normalized, and the actor fields
(`owner`, `createdBy`, `updatedBy`) collapse to `<actor>`, because a replay
runs as a different user on purpose. Collections and HTML views are asserted by
status only — their contents depend on whatever else the database holds. The
ad-hoc runner reports the same comparison as a `[content]` line.

### Replaying on another database

Ids returned by create operations are captured from the recorded response
bodies and rebound: the generated test assigns them to variables (`world_1`,
`character_1`, …) and the later requests reference the variables, so the test
runs on any database. Objects the session referenced but did not create are
listed in the docstring as preconditions.

- `harness replay export <session> --mode backend --bundle <dir>` also writes
  each referenced world as a content bundle (via the dev export API).
- `harness replay run <session> [--bundle <file>]…` imports the bundles and
  replays the requests against a running app (the dev stack, or `--base-url`),
  binding the created ids at runtime and reporting expected versus actual
  status for every step. Use it to try a recording on your database before
  turning it into a committed test.

### Recording outside development

Recording is always available in development. Elsewhere it exists only when
`replay.enabled` is set in the configuration, and starting or stopping it
requires an admin — the toggle in the user menu (visible to admins) calls the
API. Emails and user names are anonymized at write time with deterministic
per-session pseudonyms (`mario@x.it` → `user-1@example.test` everywhere in the
session), and tokens/passwords are replaced with `<redacted>`. The pseudonym
mapping lives only in the worker-shared recording config, never in the
recording files.

## How it is built

- **Browser side** — `src/frontend/static/js/replay.js`, loaded when recording
  is available (`replay_enabled` catalog global). It chooses a stable selector
  per click (`data-testid`, `id`, `a[href]`, then the text) and skips the click
  when there is none, because the navigation it caused is recorded as a `goto`.
  Steps go out one batch at a time in a sequential queue: `sendBeacon` does not
  guarantee ordering. The toggle now also starts and stops the backend
  recorder through the API.
- **Backend side** — `src/backend/replay/middleware.py`, a pure ASGI middleware
  (bodies must be read and handed on unchanged, which `BaseHTTPMiddleware`
  makes awkward). It records only while a typed JSON config names a session;
  exclusions and write-method filtering happen before a request body is read.
  Response bodies are captured up to 64 KiB. `anonymize.py` replaces emails,
  user names and tokens before anything is written.
- **Storage** — `harness-artifacts/replay/` (ui) and `.../backend/`, mounted
  into both stacks. Routes live in `src/backend/replay/routes.py` under
  `/api/replay/*`: start/stop are admin-only, and outside development the
  whole feature requires `replay.enabled` in the configuration.
- **Generation** — `src/harness/replay.py` turns steps into a typed plan
  (`plan_backend`), and both the test generator and `replay run` consume that
  plan. It is a pure function, unit-tested without a browser or a database.

## Notes and limits

- Ids created during the session are rebound; ids that predate the session are
  listed as preconditions and must be imported (`--bundle`) or the steps that
  touch them fail.
- The generated tests assert the recorded statuses, nothing more about
  content — add the assertions that matter.
- `harness replay run` authenticates with the dev login, so it targets a
  development or test instance; replaying against production is not supported
  by design.
