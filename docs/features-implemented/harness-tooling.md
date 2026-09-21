# Comparing the app with the prototype, and the dev loop

Tools that make "does this look like the prototype" and "how fast can I see a
change" answerable without guessing.

## What it does

- `harness compare /worlds/<id>` renders an application page and the prototype
  page it must match, at the same viewports, and writes a side-by-side HTML
  report plus a pixel diff. The percentage is a signal, not a gate
  (`--fail-on-diff` makes it one). `--base-url` points it at the dev showcase
  instead of the harness environment. Entries in `seed/prototype_map.yaml` can
  declare `landmarks` (semantic app/prototype selector pairs); the report then
  gains a structural section that explains differences in geometry terms —
  width divergence, vertical displacement, page overflow, missing landmarks,
  font family changes, and sub-44px touch targets on phone.
- `harness prototype serve` opens the static prototype next to the app.
- `harness browsers` installs Playwright's Chromium into the repository.
- `harness screenshot --base-url …` captures a page at desktop and phone width.
- `harness test e2e --fresh` destructively resets only the E2E test database
  (`backend_e2e_test`) and clears that environment's uploads before running.
  Integration tests use a separate `backend_integration_test` database in the
  same PostgreSQL container, so the two suites — and a fresh E2E — can run in
  parallel without interfering. Neither touches the scratch or showcase
  databases; all earlier data in the E2E environment is lost.
- Browser journeys use `BrowserSession.expect_api(...)` after writes to assert
  persisted server state instead of trusting optimistic text in the page.
- `harness doctor` checks state, ports, Postgres readiness and connection usage,
  backend health, Playwright, and forgotten replay recording without exposing
  environment values.
- `harness smoke` authenticates and visits the main and world pages, failing on
  HTTP or browser errors. `harness logs` filters Compose output by structured
  request/trace id in Python.
- `harness env up --recreate` repairs changed containers without discarding
  failed-start state; `harness dev up --no-build` skips an unnecessary rebuild.
- `harness artifacts list|show|clean` inspects and prunes artifact runs. Every
  artifact-producing command (screenshot, compare, component tests) writes into
  `harness-artifacts/<run-id>/` with a manifest recording command, revision,
  status and files. `clean` is a dry run unless `--apply` is passed and never
  deletes running or pinned runs (or the latest failure, unless `--force`).

## How it is built

- `src/harness/commands/compare.py` maps an app path to a prototype page through
  `seed/prototype_map.yaml`, serves the prototype on an ephemeral port, captures
  both sides and writes the report; `src/harness/test/compare.py` computes the
  diff in Chromium (canvas), so no image library is needed.
- The structural section measures each landmark in the live page
  (`src/harness/test/landmarks.py`): rect, display, font, gap, padding, border
  and overflow, plus the page's scroll/client width. Landmarks are explicit
  selector pairs in the map — nothing is inferred from the DOM, and no selector
  depends on the Italian copy. The pixel diff is unchanged.
- Integration and E2E each get their own database in the single test PostgreSQL
  container. `src/harness/test/databases.py` creates both idempotently through
  the container superuser (init scripts only run on an empty volume) and the
  harness generates per-target env/config under its state directory, so the
  shared `test.env` cannot override which database a suite uses. `--fresh`
  drops and recreates only the E2E database after checking its name.
- `src/harness/artifacts.py` owns the artifact layout: run ids are validated,
  artifact names cannot escape the run directory, and cleanup refuses paths
  outside the root. Integration test uploads go to
  `harness-artifacts/uploads/` (configured in the generated test config) instead
  of the repository's `data/`; E2E uploads stay in the container volume.
- `docs/features-request/prototype_map.md` records which JinjaX component
  renders each prototype construct, and how faithful it is.
- The browser lives in `.playwright-browsers/` (gitignored): Playwright's default
  `~/.cache` location is pruned by some environments, which re-downloaded it on
  every run.
- Both stacks run the backend with `--reload`; the reload excludes
  `**/__pycache__/**`, because running pytest writes bytecode under `src/` and
  the reloader restarted the app mid-suite.

## Notes and limits

- The prototype's data is hardcoded and different from the reference world, so
  the comparison judges structure, typography and spacing, not the text.
- `harness compare` needs the harness Docker environment for the app side unless
  `--base-url` is given.
- Replay recordings stay in `harness-artifacts/replay/`: the backend middleware
  writes them from inside the container, so they are a shared inbox rather than
  a per-run artifact.
