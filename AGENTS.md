# Project Guidelines

This file is reserved for coding agents.
Be concise, both when talking and writing code. In general. LLMs tend to use a lot of justapoxitions when talking:
- it's not (only) X, it's Y
- it's this thing that should be done with a explicit decision, not with other patches
Please, avoid this unless it makes sense to write like this. the second example especially could have stopped at the comma, you are adding useless words that don't say anything new.
Every line of code is a potential liablity, so a solution should not add useless complexity.
Don't fragment code into a million private helpers, especially ones used by a single function: promote reuse, not fragmentation. If a snippet is not easy to follow, prefer a comment over extracting it.
A change done in a file in general should not have a ripple effect on a very distant unrelated file.
If there is a bug, the bug should be as much as possible local to the place where it happened.
Do not use `getattr` or `setattr`. Use explicit typed attributes.
Use Pydantic models instead of untyped dictionaries for domain data and internal boundaries.
DO NOT COAUTHOR THE COMMITS
Never ask questions through multiple-choice polls: ask in plain prose.

## Working process

**Large changes are tickets.** Split a big change into tickets and finish each
one on its own — implement it, test it, commit it — before starting a dependent
ticket. A large change is never delivered as a single commit. Independent tickets
may run concurrently only through the approved workflow below.

### Delegation and parallel tickets

- For a long ticket list, evaluate whether subagents would keep research and
  implementation details out of the coordinating agent's context.
- Check dependencies, shared files, shared configuration, and test-environment
  isolation before proposing parallel implementation. When tickets are
  independent and conflicts are unlikely, consider N agents in separate git
  worktrees, one ticket per worktree.
- **Ask the user before launching subagents or creating parallel worktrees.**
  Propose which tickets to delegate, which can run concurrently, the number of
  agents, and how results will be integrated. Do not assume delegation or
  parallel execution is the default. Until approved, work sequentially yourself.
- Give each approved subagent the ticket, relevant paths and conventions,
  previous decisions, verification requirements, and explicit edit boundaries.
- Separate worktrees do not automatically isolate ports, databases, uploads, or
  harness state. Verify that isolation before running concurrent test suites;
  do not reset or tear down another agent's environment or the user's showcase.
- The coordinating agent reviews each diff and verifies the result independently.
  Integrate tickets in dependency order, with one commit per ticket and the
  required tests and visual checks. A subagent's completion report is not proof
  that the ticket is done.

### Shared workflow

- After a context compaction, re-read `docs/features-request/*.md` before continuing.
- All source is English, including URL paths and endpoints. Only the UI copy is
  Italian.
- A ticket is done only with a passing test and a desktop + phone screenshot
  compared against `prototypes/devin-prototype/`.
- Document what is built: one short file per feature in
  `docs/features-implemented/` — what it does, how it is built, its limits.
  Human-sized, not a changelog. Specs and problem lists live in
  `docs/features-request/`.

### Planning and releases

- Requests use stable numeric IDs and Markdown frontmatter; feature manuals keep
  thematic names. Many tickets require individual outcomes, not a new feature
  manual per ticket. Update an existing manual when the same capability evolves.
- Vikunja is the chosen authority for backlog and current ticket status. The
  repository owns specifications, decisions, feature manuals and release notes.
  Do not manually mirror live status in both places.
- Kanboard is a retained comparison deployment, not a second backlog. Target
  Vikunja's API for future ticket tooling. The existing demo cards have simulated
  states; do not treat them as real requests or import them into the real backlog.
- Choosing Vikunja does not authorize deleting Kanboard's data, migrating the
  historical backlog, or assigning release versions.
- Towncrier with Markdown fragments is the selected release-note approach;
  its tooling is not configured yet. Ask the user to choose the version at
  release time. Never infer or apply a major/minor/patch bump without approval.
- A release may group an entire multi-ticket cycle. Git commits, board ticket IDs,
  application versions and Alembic revisions are distinct identifiers.

## Tools
If available in your environemnt, use
- haystack MCP when creating haystack pipelines
- semble: semble mcp is superfast and superaccurate searhc tool. use it instead of ytour usual tools and grep searches. use these tools only if semble did not give you an answer.

## Project Structure

Keep the repository organized by responsibility rather than listing every module here:

- `src/backend/` contains the FastAPI application. Keep each domain in a self-contained feature module.
- `src/frontend/` contains JinjaX components and static assets.
- `alembic/` contains database migrations; `deploy/` contains deployment configuration.
- `docs/` contains workflows and project-specific technical guidance.
- Root configuration belongs in files such as `config.yaml`, `pyproject.toml`, and `alembic.ini`.

A typical backend feature looks like this:

```
src/backend/<feature>/
├── routes.py       # JSON API endpoints
├── views.py        # HTML/htmx endpoints, when needed
├── schemas.py      # Request and response models
├── service.py      # Business logic and database queries
├── models.py       # SQLAlchemy models, when needed
└── exceptions.py   # Feature-specific exceptions
```

Use existing neighboring features as the source of truth. Shared infrastructure belongs in the appropriate top-level backend module, not in a feature merely because it is convenient there.

### Feature Organization

Features under `src/backend/` should be self-contained. Routes and views handle transport, schemas handle validation, and services own business logic and SQLAlchemy queries. JSON and HTML/htmx routes should share the same service layer.

### Frontend

The frontend uses [JinjaX](https://jinjax.scaletti.dev/) for server-rendered components and [htmx](https://htmx.org/) for dynamic interactions — no client-side framework. The [`json-enc`](https://github.com/bigskysoftware/htmx-extensions/blob/main/src/json-enc/README.md) htmx extension encodes form submissions as JSON payloads.

- **`common/`** — Reusable primitives, no domain knowledge: Button, Card, Field, Dialog, Alert, Divider, Pill, Table, Icon, Avatar, Menu, Tooltip, ChoiceGrid, ButtonGroup, Grid, VStack, HStack, IconButton, MediaFrame, EmptyState, Switch, Tabs, SaveIndicator, Combobox
- **`editorial/`** — The product's vocabulary and its atlas identity: Masthead, Crumbs, Cover, Quick, Timeline, Plogo, Face, EntityCard, StoryCard, StoryBand, Ledger, Row, RowList, CollectionCreate, Docbar, DocIdentity, DocEdit, DocSummary, ImageEditor, Links, Metadata, SectionHead
- **`layout/`** — Page shells: BlankPage (bare HTML), Page (with the shell), Rail, Topbar, UserMenu
- **`pages/`** — Full pages composed from the three above, one folder per module

**Read `docs/frontend_guide.md` before touching the frontend.** It holds the
folder rules, the anatomy of a component, the token rules, the checklists for
adding or changing a component, and the test commands. `docs/design_guide.md` is
the portable process behind the visual language (reusable on other projects),
`docs/features-request/frontend.md` holds the settled visual decisions, and
`docs/jinjax.md` is the JinjaX mechanics reference.

Each new module generally gets its own page.

## Testing

Unit testing is rarely useful for API development since most API calls are a chaining of simple operations. Prefer integration tests and avoid mocks except for external services.

- **Unit (ms):** Test pure logic only; use integration tests for database-dependent code.
- **Integration (s):** Use a real database and FastAPI's test client; verify behavior and database state.
- **E2E (s–min):** Test complete workflows as a black box without mocks.
- **Fuzzy/performance (min+):** Add these when robustness or load behavior matters.
- After a browser action writes data, assert the persisted result through the API
  or an integration database query; visible editor/DOM text is not proof of a save.

### Test Harness

Use the `fastapi-template-test-harness` MCP tools when available. Otherwise use `uv run harness`. Do not manually start Uvicorn or modify `config.test.yaml` for testing: the harness manages isolated environments, configuration, and dynamic ports.

- Unit: `test_unit` or `uv run harness test unit`
- Integration: `env_up(mode="local")`, then `test_integration`, then `env_teardown`
- E2E: `env_up(mode="docker")`, then `test_e2e`, then `env_teardown`

## New Feature Workflow

Work in small increments: implement one layer, test it, then move on. Do not write the whole feature in one pass.

### Modifying an existing feature

1. Understand what needs to change and where it lives.
2. Make the smallest change that moves toward the goal.
3. Add or update tests for that change.
4. Run the tests. Repeat until the feature is done.

### Creating a new feature

1. Create the feature module under `src/backend/<feature>/` (see the structure above).
2. Add the SQLAlchemy model, then the schemas, exceptions, service, and routes — one layer at a time, testing each before continuing.
3. Register the router in `server.py`.
4. Add the frontend: a new page, and a new component only if no existing one fits. Reuse `common/` and `layout/` primitives as much as possible.
5. If the feature needs functionality from another module, call that module's service (preferred) or repository — do not duplicate its logic.

### Tests

Cover happy path, error path, and any non-trivial case (concurrent access, partial input, external dependency failure). See `docs/new_feature_workflow.md` for the detailed checklist.

## Database and Migrations

This project uses **PostgreSQL** with **Alembic** for schema migrations and a **two-role security model**:

- **`migrator_user`**: Owns the schema, runs migrations (DDL rights)
- **`app_user`**: Runtime application user (DML only - no table creation/modification)

### Key Principles

- ✅ **All table management MUST be done through Alembic migrations**
- ❌ Never use `Base.metadata.create_all()` in production
- ❌ Never grant DDL rights to the runtime application user

### Quick Migration Workflow

1. Define your SQLAlchemy model in the relevant feature module, e.g. `src/backend/users/models.py`
2. Ensure the model registry is updated by the model registry pre-commit hook
3. Generate migration: `uv run alembic revision --autogenerate -m "description"`
4. Review the generated file in `alembic/versions/`
5. Apply migration: `uv run alembic upgrade head` (or restart Docker)

See **`docs/database_migrations.md`** for complete documentation on:
- Database architecture and security model
- Configuration files (`.env`, `config.yaml`, `config.docker.yaml`)
- Detailed migration workflows
- Best practices and troubleshooting

## Local harness (learned)

The harness drives a real Postgres via docker/podman and is the only supported
way to run integration tests and browser checks.

```bash
uv run harness dev up                     # dev stack: scratch 8001 + showcase 8002
uv run harness dev reset --db show        # recreate the showcase DB + seed it
uv run harness env up --mode local        # database only, for integration tests
uv run harness test integration           # uses the active environment
uv run harness test frontend              # component tests: real JinjaX in Chromium, no backend
uv run harness env up --mode docker       # database + backend container
uv run harness test e2e --fresh           # reset only the E2E DB/uploads, then run E2E
uv run harness doctor                     # environment, ports, DB, browser, replay checks
uv run harness artifacts list             # artifact runs; `show <id>`, `clean --keep-latest N [--apply]`
uv run harness material check             # offline: M3 token inventory vs main.css
uv run harness smoke                      # authenticated main-page checks
uv run harness logs --request-id <id>     # filter structured compose logs
uv run harness screenshot /worlds --email e2e-admin@example.com --name worlds
uv run harness compare /worlds/<id>       # app vs prototype report + pixel diff
uv run harness env teardown
```

- Three environments, never mixed:
  - **test** — `harness env up` / `harness test`, `config.test.yaml` + `test.env`,
    two isolated databases in one PostgreSQL container:
    `backend_integration_test` (integration) and `backend_e2e_test` (Docker
    backend + E2E). Tests create and drop worlds here; the suites can run in
    parallel and `--fresh` only ever resets the E2E one.
  - **work** — `harness dev up`, `config.yaml`/`config.docker.yaml` + `.env`,
    database `root_gdr_dev`, app on **8001**. The agent's scratch space.
  - **showcase** — same stack, database `root_gdr_show`, app on **8002**. What is
    shown to the user; `harness dev reset --db show` recreates it and seeds only
    the reference world.
- `harness dev up` starts both apps with reload on (`--no-reload` turns it off).
  `harness dev seed --db work|show` migrates and seeds one database; `reset`
  drops the schema first.
- `harness dev reset --db show` run against an already-serving stack can answer
  the seed's first request with a 500: dropping the schema invalidates asyncpg's
  prepared-statement plans and the pool only clears them once it has seen the
  error. Run the reset again (or restart the app) and it seeds cleanly — this is
  not an application failure.
- `.env` (gitignored) holds the dev database names and `AUTH__JWT_SECRET`; copy
  `.env.example` and add a dev secret if it is missing.
- `harness compare` pairs an application page with its prototype page (see
  `seed/prototype_map.yaml` and `docs/features-request/prototype_map.md`) and writes
  `harness-artifacts/compare/report.html`. The pixel percentage is a signal, not
  a gate (`--fail-on-diff` makes it one).

- The committed `test.env` is preferred over `.env.test`; the harness and
  `tests/conftest.py` both read it, so a fresh checkout runs tests without
  private secrets.
- Direct pytest/alembic runs need the active environment's config, and the env
  file must match the target database (env vars override the YAML):
  `ENV_FILE=~/.cache/fastapi-template/harness/<worktree>_<hash>/test.integration.env YAML_CONFIG_FILE=.../config.test.integration.local.yaml`
  (use `test.e2e.env` + `config.test.e2e.local.yaml` for the E2E database).
- Playwright's browser is installed with `uv run harness browsers` into the
  repository (`.playwright-browsers/`, gitignored). Do not use
  `playwright install` directly: the default `~/.cache` location is pruned by
  some environments, which re-downloads it on every run. Re-run after a
  playwright bump.
- Screenshots land in `harness-artifacts/<run-id>/` (gitignored) with a
  manifest; pass `--output-dir /tmp/...` when the agent needs to read them back
  (the artifacts area is not readable by tooling).
- Bind mounts in the test compose files use `${HARNESS_REPO_ROOT}` and `:z`
  because podman-compose resolves relative volume paths against the cwd and
  SELinux blocks unlabelled mounts (the app would silently fall back to
  `localhost` for the database).
- `dev login` (`POST /auth/dev-login`) sets the same cookies as a real login;
  browser contexts are authenticated through it.

## Replay (learned)

Turn a bug found by hand into a reproducible test, from either side:

- **Browser steps** — open the user menu and switch on **Registra azioni**
  (admin), then work normally; every page, field and click is recorded.
- **Backend calls** — `uv run harness replay start` (the middleware records
  each request plus its response body), work, then `uv run harness replay stop`.
- `uv run harness replay describe <session> --name "…" --description "…"` names a
  recording (editable any time); the name becomes the generated test's function
  and file name, the description its docstring.
- `uv run harness replay list|show|export <session> [--mode ui|backend]`;
  `export` writes a Playwright test (ui) or an integration test (backend) into
  `tests/e2e/` or `tests/integration/`. Ids created during the session are
  rebound, so the backend test runs on any database; it asserts the recorded
  statuses and, for JSON object responses, the body with UUIDs, timestamps and
  the actor normalized.
- `uv run harness replay run <session> [--bundle <file>]…` replays a recording
  against the dev stack (or `--base-url`), importing precondition bundles and
  reporting expected vs actual status per step.
- `export --bundle <dir>` writes each referenced world as a content bundle, so
  a recording can move between environments.
- Recordings live in `harness-artifacts/replay/` (gitignored) and are mounted
  into both stacks. Recording is always on in dev; elsewhere it needs
  `replay.enabled` and an admin. Emails, user names and tokens are anonymized
  at write time.

## Content harness (learned)

```bash
ENV_FILE=$PWD/test.env YAML_CONFIG_FILE=config.test.yaml \
  uv run harness content seed --email e2e-admin@example.com
uv run harness content export <world-id> --email <email> -o /tmp/bundle.yaml
uv run harness content import /tmp/bundle.yaml --email <email>
uv run harness content rebuild --email <email> [--world <world-id>]
```

- `seed` imports the committed reference world (`seed/boschetto-di-smeraldo.yaml`)
  by default; `--file` imports another bundle. The YAML is the shared dataset for
  screenshots, the visual comparison and e2e tests.
- Export/import are idempotent: the world matches by name, content by its
  natural key (name, or slug for pages), so a round trip updates instead of
  duplicating. In dev, the same bundle is available over the API at
  `/api/dev/worlds/{id}/export` and `/api/dev/worlds/import`.
- Pass `ENV_FILE`/`YAML_CONFIG_FILE` to point the CLI at the test database;
  without them it uses `config.yaml` (the dev database).
