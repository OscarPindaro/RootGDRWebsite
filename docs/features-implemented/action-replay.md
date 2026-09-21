# Record what you do and generate a test

A bug found by hand should become a test that reproduces it, without writing the
test by hand.

## What it does

Two recordings, both dev-only:

- **Browser steps.** Switch on *Registra azioni* in the user menu and work
  normally. Each page, field and click is recorded as a semantic step ("filled
  `name` with X", "clicked the link to `/worlds/new`").
  `harness replay export <session>` writes a Playwright test.
- **Backend calls.** `harness replay start`, work (even with curl), then
  `harness replay stop`. Every request and its response status is recorded, and
  `harness replay export <session> --mode backend` writes an integration test
  that replays them and asserts the statuses. Start with `--read-only` to keep
  only GET, HEAD and OPTIONS, and repeat `--exclude /path` to omit path prefixes.

`harness replay list` and `show <session> [--mode ui|backend]` inspect a
recording. `harness replay diff <before> <after> --mode ui|backend` reports
added, removed and changed steps. Complete ISO timestamp values become
`<timestamp>` and UUID substrings become `<uuid>` recursively in the comparison
key; export and replay retain the recorded values.

## How it is built

- **Browser side** — `src/frontend/static/js/replay.js`, loaded only when
  `env == "dev"`. It chooses a stable selector per click (`data-testid`, `id`,
  `a[href]`, then the text) and skips the click when there is none, because the
  navigation it caused is recorded as a `goto`. Steps go out one batch at a time
  in a sequential queue: `sendBeacon` does not guarantee ordering, and a click
  recorded before the field it followed produced a test that replayed the wrong
  sequence.
- **Backend side** — `src/backend/replay/middleware.py`, a pure ASGI middleware
  (the body must be read and handed on unchanged, which `BaseHTTPMiddleware`
  makes awkward). It records only while a typed JSON config names a session, so
  every worker sees the same read-only and exclusion settings. Exclusions and
  write-method filtering happen before the middleware reads a request body.
- **Storage** — `harness-artifacts/replay/` (ui) and `.../backend/`, mounted into
  both stacks. The routes are `src/backend/replay/routes.py`, registered only
  under `env: dev`.
- **Generation** — `src/harness/replay.py` turns steps into source; it is a pure
  function, so it is unit-tested without a browser or a database.

## Notes and limits

- Recorded ids and payloads come from where it was recorded, so a replay runs
  there unless adjusted; a write may need a fresh world to run twice.
- The generated tests assert nothing about the content — they reproduce the
  journey. Add the assertions that matter.
- `harness replay stop` logs in first, so that login appears as the last step.
