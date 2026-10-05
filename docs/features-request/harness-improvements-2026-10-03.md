---
id: REQ-0011
requested_on: 2026-10-03
title: Harness follow-up and reproducible development setup
---

# Harness improvements — 2026-10-03

Follow-up tickets from the frontend mega-plan retrospective. H1–H7 and the
Node/axe setup extension were approved in the 2026-10-03 infrastructure and
document cycle. The filename is retained for existing links. Ticket keys are
REQ-0011/T01–T07, with H1–H7 as stable aliases; T08 covers Node/axe setup.
Current implementation status belongs in Vikunja.

## Decisions and priority

| Ticket | Topic | Scope decision |
|---|---|---|
| H1 / T01 | Pass pytest arguments through `harness test` | Approved; first harness priority |
| H2 / T02 | Validate prototype-map landmarks | Approved; structural gate, not pixel gate |
| H3 / T03 | Document known test failures | Approved; Markdown evidence, no skip/xfail |
| H4 / T04 | Capture screenshots after UI transitions settle | Approved; bounded settling |
| H5 / T05 | Check frontend payload budgets before commit | Approved; reuse existing thresholds |
| H6 / T06 | Consistent Playwright browser location | Approved; preserve explicit overrides |
| H7 / T07 | Ruff in development dependencies | Approved; match the hook pin |
| T08 | Install locked Node/axe dependencies for E2E setup | Approved; no missing-dependency skips |

The delegation strategy is recorded in `AGENTS.md`. The approved cycle permits
flexible waves of up to three isolated worktrees after Root GDR/Vikunja bootstrap,
with coordinator review and independent verification. Recheck the current code
before each ticket: the retrospective describes a previous session.

## H1 — Forward pytest arguments through the test CLI

**Problem:** `src/harness/commands/test.py` exposes whole-suite commands only.
`src/harness/test/runner.py` already accepts selectors and typed `PytestOptions`,
including keyword filtering and failure limits; preserve and reuse that logic.

**Change:** support trailing pytest arguments after `--` for unit, frontend,
integration and E2E. Keep harness options such as `--fresh` before the separator.
The intended interface, not available yet, is:

```bash
uv run harness test e2e --fresh -- -k face_pickers -x --tb=long
uv run harness test frontend -- tests/frontend/test_field.py -q
```

**Acceptance:**
- Quoted `-k` expressions, test paths and node ids arrive as argument tokens,
  never as a shell command string.
- An explicit selector runs only the selected tests, not the default directory
  plus those tests. No arguments preserves the existing whole-suite behavior.
- Suite boundaries, database configuration, environment checks, artifacts and
  pytest exit status remain intact. `--fresh` resets only the E2E environment.
- Tests cover parsing, command assembly, invalid selectors and exit propagation.

## H2 — Fail clearly when a mapped landmark is missing (approved minimal scope)

**Problem:** `seed/prototype_map.yaml` pairs app routes with prototype pages and
optionally names page regions with CSS selectors. `app:` is the selector in the
running application; `prototype:` names the corresponding prototype region.
A renamed class can leave the mapping pointing at nothing.

**Change:** reuse the existing browser measurements and structural diagnostics
in `src/harness/commands/compare.py`. They already report missing landmarks;
add a dedicated check or strict option that returns failure when a required
mapped region is missing. This requires a rendered browser page, not a
unit-only inspection of template source.

**Acceptance:** report route, viewport, landmark, side and selector; distinguish
missing/ambiguous matches from geometry differences. Check desktop and phone
using reference content and suitable permissions, without demanding that a
phone's closed drawer be visible. A fixture with a stale selector fails;
correct selectors pass. Ordinary pixel differences are not the failure gate.

## H3 — Record known failures without hiding regressions (approved minimal scope)

**Start small:** use a Markdown note under `docs/features-request/problems/`,
as `pre-existing-e2e-failures.md` already does. Each entry names the exact test,
symptom, reproduction, evidence that it predates the current work, related
ticket and date. Close entries when fixed; never rely on a memorized total of
expected failures.

**Acceptance:** another agent can distinguish an existing failure from a new
one using that note. A known failure still makes the test run fail. Automated
runner exceptions or strict `xfail` are a separate proposal requiring approval;
this ticket must not add skips or convert failures into passing results.

The earlier retrospective proposed a machine-readable registry as well. That
extra mechanism is not approved and is not required for the Markdown version.

## H4 — Wait for screenshot-relevant UI transitions

**Problem:** a capture immediately after opening a drawer can show it midway
through its slide, creating a misleading visual defect.

**Change:** add a bounded settling mechanism to screenshot capture and reuse it
in comparisons. Prefer waiting for the affected finite transitions/animations
and required layout/font readiness. An explicit `--settle` override may cover
exceptional cases; avoid unconditional long sleeps or disabling motion globally.

**Acceptance:** a drawer/dialog capture is fully open, including at 390×844;
no-action captures remain fast; perpetual animation or a stalled request cannot
hang the command. Tests reproduce a delayed transition and verify the final
geometry is captured. Preserve console-error reporting and artifact manifests.

## H5 — Run the existing payload-budget check before commit (approved minimal scope)

**Problem:** `tests/unit/test_payload_budget.py` limits the byte size of selected
CSS, JavaScript, fonts and icon markup, including gzip measurements. Today this
runs with the unit suite; a heavy asset can be committed if that check is missed.

**Change:** invoke the same check in pre-commit when relevant assets, icon
registry or budget definitions change. Reuse its measurements and thresholds;
do not create a second set of limits or raise existing limits to pass.

**Acceptance:** offline and deterministic; reports the asset group, measured
size and limit; an oversized fixture fails. Unrelated commits skip the check.
Document its existing scope: these are selected committed-file measurements,
not a complete browser transfer measurement of every page or component asset.

## H6 — Use the repository's Playwright browsers consistently

**Problem:** `src/harness/test/browser.py` sets `PLAYWRIGHT_BROWSERS_PATH` to
`.playwright-browsers/`, but `tests/frontend/conftest.py` does not explicitly
establish that default. Direct pytest can therefore look in another cache.
`setup.sh --harness` also currently calls `playwright install chromium` directly.

**Change:** reuse one lightweight source of truth for the browser location in
the harness and frontend fixtures. Respect an explicitly supplied environment
variable. Check setup/install behavior against `uv run harness browsers` so
installation and execution use the same location.

**Acceptance:** after the supported browser installation, both direct frontend
pytest and the harness launch Chromium without a manual environment prefix.
Explicit overrides survive; no redundant browser download or whole harness
reinstallation is required. Verify from a working directory other than the
repository root as well.

## H7 — Make Ruff available outside pre-commit

**Problem:** Ruff is supplied by `ruff-pre-commit`, but is absent from the `dev`
group in `pyproject.toml`. Agents cannot run the same lint/format checks before
committing, so hooks repeatedly rewrite files and require another commit attempt.

**Change:** add Ruff through the package manager to development dependencies and
update the lockfile. Match the hook's pinned version (`v0.15.1` at the time of
this note), or explicitly justify a coordinated update. Leave hooks enabled.

**Acceptance:** a fresh `uv sync --dev` supplies `uv run ruff check` and
`uv run ruff format --check`; their behavior agrees with pre-commit on fixtures.
No production dependency or unrelated formatting changes are introduced.

## T08 — Locked Node/axe dependency setup

`tests/e2e/test_accessibility.py` loads the local
`node_modules/axe-core/axe.min.js`. The dependency is already declared in
`package.json`; `setup.sh` currently does not install the Node dependencies.
Install the lockfile's Node dependencies with `npm ci` when harness/E2E tooling
is requested. Do not skip accessibility checks when the dependency is missing,
add unrelated dependencies, or reinstall agent/MCP configuration to fix assets.

Acceptance: setup works from a clean checkout and another working directory;
axe is available and Chromium uses the supported harness location. CI performs
explicit dependency setup without installing global agent configuration.

## T09 — Keep database preparation intact during recreation

Follow-up found while verifying the approved cycle; evidence and reproduction
are in [the recreation regression](problems/harness-recreate-database.md).
The final backend startup must target `app` with `--no-deps`, so a database
already recreated, initialized and migrated is not recreated a second time.

Acceptance: command-assembly regression fails before the fix; an actual owned
Docker environment retains both integration/E2E databases and Alembic schemas
after `env up --recreate`. Test recovery never resets work, showcase or board
storage, and no exception converts an unavailable database into a passing test.

## T10 — Complete the development environment template

Follow-up found while continuing the cycle on a fresh checkout. Copying
`.env.example` leaves the development stack unusable: `harness dev up` fails
because `DEV_SHOW_DB` is missing, and `harness dev seed` cannot create the
bootstrap admin because `AUTH__BOOTSTRAP_ADMIN_EMAIL` is unset; the app and the
htmx payload hook also require `AUTH__JWT_SECRET`. The example still carried
the pre-stack database name.

**Change:** declare every key the development stack requires in
`.env.example`, with development-only placeholder values and the documented
`root_gdr_dev`/`root_gdr_show` database names.

**Acceptance:** a unit test keeps the example aligned with the doctor's
required dev keys plus the two auth keys; an environment with exactly those
additions starts the stack and seeds the work database.

Keep the retrospective as historical context; these tickets and the approved
cycle decisions define the implementation scope.
