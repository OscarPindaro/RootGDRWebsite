# Project recipe

Use approved project instructions as the source of architecture and workflow.
For this repository, consult the [feature workflow](../../../../docs/new_feature_workflow.md),
[backend guide](../../../../docs/fastapi.md),
[schema guide](../../../../docs/schemas.md),
[database guide](../../../../docs/database_migrations.md),
[testing guide](../../../../docs/testing.md) and
[frontend guide](../../../../docs/frontend_guide.md).
Read the target project's own instructions first when working elsewhere.

## Technical foundation

Use the approved Python version and uv/lockfile conventions. The current
reference project uses Python 3.14. Check manifests and compatibility before
selecting dependency versions; do not silently upgrade an existing project.

Keep responsibility within feature modules under `src/backend/<feature>/`:
routes and views handle transport, schemas validate boundaries, services own
business behavior and database queries, models define persistence, and
exceptions describe feature failures. Shared infrastructure stays outside
individual features. Do not add every file unless the feature needs it.

Use Pydantic at internal boundaries and typed SQLAlchemy models with the
established async-session conventions. Alembic owns schema changes.
Keep bootstrap/migration credentials separate from DML-only application access.
Do not replace the project's ORM approach with a global SQLAlchemy Core
repository layer merely because an upstream scaffold used one.

Choose configuration, authentication and logging from approved requirements
and existing implementations. Private libraries, OIDC setup, telemetry export,
credential creation and hosting are separate choices. Do not fabricate missing
integrations or depend on unavailable skills.

## Frontend technology and direction

Use server-rendered JinjaX components and htmx for web UI. Preserve semantic
HTML, accessible controls, existing token ownership and component composition.
Follow the target project's frontend guide and approved visual references.
Do not switch technology to accommodate a visual exploration.

The UI philosophy is expected to evolve through a later approved request.
Do not invent that request, create its ticket, implement proposals or encode an
unapproved new philosophy here. Existing settled guidance remains the reference
until superseded. Technology stays JinjaX/htmx; the later skill update concerns
design philosophy, not a framework migration.

For a new product, agree on its audience, first flow and visual direction
instead of copying Root GDR's atlas identity or business components wholesale.
Do not introduce a new asset pipeline or packaging workflow by default.

## Workflow and proof

Reuse an explicitly approved starter/template when available. Otherwise plan
and implement a minimal foundation; this port does not ship prebuilt templates.
Never copy local secrets, user accounts, uploaded data, machine configuration or
the reference world's domain data into another project.

Separate idea intake from implementation. Follow the target's tracking tools
without creating a new board or duplicating live status. Use small independently
verified tickets or batches and preserve dependencies.

Establish test commands and isolated environments in the foundation. Prefer
real PostgreSQL integration tests and black-box workflows; unit tests cover
pure logic and mocks remain at external-service boundaries.
In this repository, only the harness starts test applications and manages test
configuration. Do not run ad-hoc Uvicorn or reset shared environments.
For another project, define and approve its equivalent isolation before running.

Implement and test one feature layer at a time. Reproduce regressions before
fixes and preserve green characterization tests during refactors. After every
browser write, assert persisted state through an API read or integration query.
Exercise error paths, permissions and relevant concurrency cases.

Verify desktop and phone behavior against the approved references. Record
commands, outcomes and unverified prerequisites. Missing database, browser,
credentials or dependencies are blockers, not passing checks.

Keep `AGENTS.md` focused, specifications and feature manuals in their existing
homes, and chronicles optional. Follow repository release tooling and version
approval. Commit completed changes after verification under the project's
rules; no co-author attribution, push or deployment is implied.
