---
name: align-stack
description: "Audit or migrate an existing Python project to the team uv, quality, Docker, CI, and release stack."
argument-hint: "[check] [project path]"
triggers: [user]
---

# Align Stack

Follow the [development workflow](../using-development-skills/SKILL.md).
This command uses the supplied team standard, not an inferred replacement.
Report conflicts with repository rules and obtain approval before changing those
rules. Installing or inspecting this skill does not authorize a stack migration.
Ask questions in plain prose. Preserve existing release tooling unless its
replacement is explicitly approved. Destructive actions and external writes
require specific authorization, including commands suggested by the references.

Align supporting files without redesigning the application. `check` is read-only; no argument means inspect, plan, approve, then apply. Only Python has a team contract. The preflight auto-detects **libraries vs services** and relaxes the service-only invariants for libraries (see the Library section below and stack.md's **Libraries** section).

## 1. Locate and measure

Accept empty (apply cwd), `check [path]` (read-only), or `[path]` (apply target); reject anything else. Require a root/backend Python project with `pyproject.toml` or root `requirements*`; otherwise stop without writes.

Run:

```bash
bash "<skill-base-dir>/scripts/preflight-python.sh" "<target>"
```

Exit 0 means supporting-stack parity, 1 backlog, and 2 invalid input. In
`check` mode, keep the report; for a containerized ASGI service also run the
read-only runtime inventory below, then return both without writes.

## 2. Load the contract

Read the [Python index](../../shared/conventions/python/index.md) and [stack rules](../../shared/conventions/python/stack.md). Never copy kickoff templates. Consult the reference repo only when these rules cannot settle an important choice for the target.

For a containerized ASGI service, also read the
[backend conventions](../../shared/conventions/python/backend.md) and
[runtime patterns](../../shared/conventions/python/patterns/runtime-patterns.md).
Inventory the production command, PID 1 and signal path, settings ownership,
worker adapter, preload behavior, logging hook, deployed code-version source,
and every lifespan-owned background job. Flag a direct
`uvicorn.workers.UvicornWorker`, application imports in Gunicorn's master, a
CPU-derived worker formula, or multiple conflicting server commands.

## 3. Plan the target-specific merge

Follow the full [development loop](../../shared/development-loop.md) and use the stack rules as the agreed direction. Decide the project root, dependency class, Python version, entrypoint, Make targets, runtime version mirror, Docker/CI approach, import layers, deletions, and checks.

Before replacing CI:

<!-- TODO(circeus): name the team-owned shared-actions repository; `example-org/shared-github-actions`
is a placeholder, and it is the same repository as the shared reusable workflow in the stack conventions. -->
- Treat the team-owned shared-actions repository as the one
  reference exception: keep every action and reusable workflow on
  `@v2`, add a line-local `# zizmor: ignore[unpinned-uses] trusted team moving
  major`, and make Dependabot ignore its semantic-major updates. A SHA with a
  `# v2` comment does not follow the moving compatibility channel. Keep every
  other remote `uses:` reference on the stack convention's full-SHA policy.
- inventory its effective triggers, commands, build arguments, secrets, explicit resource/cache names, and every Dockerfile it can select; measure context size and generated directories;
- read called `workflow_call` inputs and preserve every non-derived value;
- Classify the CI as native orchestration, a cache-only Bake check, or an image-producing Bake pipeline before choosing cache topology;
- for persistent builders, prove repository/runner isolation and bounded GC;
- Detect overlapping feature/deploy push triggers and plan to remove accidental duplicate lint, test, build, or container execution.

Show the file matrix and preflight failures before mutation. Treat packaging and entrypoints together: keep `[project.scripts]` installable or replace it with a verified module launcher and update every documented command. Never combine an advertised project script with `tool.uv.package = false`.

For a runtime migration, make process topology and semantics explicit in the
approved plan. Preserve a target-specific worker count only when measured
capacity and failure behavior support it; never replace it with a universal
formula. Count how many times each lifespan job will run across workers and
overlapping deployment tasks. If that reveals a missing singleton or delivery
guarantee, plan the required leadership or durable messaging separately rather
than hiding the semantic change inside a mechanical stack edit. A request
limited to mechanical alignment reports this runtime gap without silently
changing it.

Preserve unrelated changes and pin intent. Do not invent architecture for import-linter.

Before changing `.dockerignore`, inspect Docker lint/test commands and their fixtures and configuration, including `env-config/`. Exclude reproducible output only after proving no selected stage needs it, then measure context size again.

Estimate formatter and autofix changes separately. Semantic or architectural fixes need another approved task.

`uv` is a host prerequisite, never a project dependency. If absent, include user-level installation in the gated plan and prove `uv --version`.

## 4. Apply and prove

Migrate in order: `pyproject.toml` → successful uv resolution → `.python-version`/`uv.lock` → Makefile/quality → pre-commit → Docker/CI/Dependabot/versioning → deletions. Keep legacy dependency/version sources while unresolved or consumed by CI. Rerun tests after mechanical autofixes.

Rerun preflight to `VERDICT: PARITY`, then run mandatory `make install` from the Python root. Prove:

- `uv --version`;
- an executable `.venv/bin/python`;
- `uv run --frozen pre-commit --version`;
- executable pre-commit and commit-msg hooks.

Keep `*.legacy` hooks only when they are real scripts with a shebang; delete other leftovers. Run the installed-hook proof without touching the real Git index:

```bash
bash "<skill-base-dir>/scripts/verify-commit-msg.sh" "<repository-root>"
```

After installation, run the exact documented application entrypoint. Prove any generated `[project.scripts]` executable. For stdio MCP, require a valid response to a minimal `initialize` JSON-RPC request, not mere startup.

When this task changes an ASGI process manager, worker, Docker command,
startup/lifespan order, logging hook, code-version wiring, or singleton
listener, run the applicable
[production-like runtime proof](../../shared/conventions/python/patterns/runtime-patterns.md#production-like-proof).
The exact Linux image is the release gate for worker replacement; a host-only
run is insufficient.

Then run `uv lock --check`, `make lint`, `make test`, `uv run --frozen pre-commit run --all-files`, and the configured Docker checks. Run Docker once from a disposable context containing only tracked and intended non-ignored files (`git ls-files --cached --others --exclude-standard`).

Verify dispatch, promote, and release workflows without running them. After changing shared or composite action inputs or their environment, search `.github/` for removed inputs and replaced paths. Report structural, installation, and quality states separately; parity alone is not completion.

After all work and verification succeed, scan the entire target. Include code, docs, developer configuration, CI, scripts, and user-facing text. Find Conda and any legacy Python environment, interpreter, dependency, or tool-handling practice that conflicts with uv. Remove or update conflicts.

Preserve stack-required `.venv` and `uv` configuration. Rerun the scan and report anything deliberately retained.

## Monorepo (Python under `backend/`)

Python project in `backend/`, a frontend alongside, deploy via `pipeline-ecs-monorepo.yml@v2`.
`a previously aligned monorepo` is the aligned reference — reuse its pattern and accept the same residual FAILs.

- **Pre-commit** lives at the repo root (git always runs hooks from there). uv hooks reach the
  project via `uv-lock` `args: [--project, backend]` and a `cd backend` entry for mypy/import-linter;
  scope the file-modifying hooks with `files: ^backend/` so frontend and docs stay untouched;
  `make install` runs `pre-commit install` from the root.
- **CI**: the preflight does not recognize `pipeline-ecs-monorepo.yml@v2`, so `effective shared
  Python CI contract` and the branch checks FAIL even when correct. Gate feature branches with
  `check-python.yml@v2` (`branches-ignore: [dev, main]`, `dockerfile: backend/Dockerfile`,
  `ssh_deps: shared-lib`, `ecr_repo_override: <prefix>-<app>-be` — the split BE repo carries the `-be`
  suffix); gate dev/main with `backend_run_lint/test: true` + `backend_dockerfile` on the deploy
  pipeline. Keep these shared-workflow references on the moving `v2` channel under the exception above.
  Do not add a self-hosted Bake check for a monorepo.
- **Docker**: root context, `backend/Dockerfile`, `COPY backend/ …`; keep the deployed stage's name
  as the shared action targets it. The root `.dockerignore` must exclude `**/.venv`, or `COPY backend/`
  overwrites the image venv with the host's. The base-pin scan covers every Dockerfile, frontend included.
- **Makefile**: the contract needs only `backend/Makefile` (the Python surface). Add a thin root
  delegator too, as the aligned monorepo reference does — `be-*` → `$(MAKE) -C backend`, `fe-*` → npm in `frontend/`, plus
  aggregate `install`/`lint`/`test` — so the whole repo is driven from the root.
- Until the preflight recognizes `pipeline-ecs-monorepo.yml@v2`, expect only the two CI failures
  named above. Do not report the `backend/` location or the `cd backend` hooks as divergences.

## Library (distributable package)

A library consumed by other projects (consumed by other projects) — `[build-system]` present, no
service `Dockerfile`, not `package = false`. The preflight auto-detects it, marks the
Docker invariants N/A, accepts a floor `requires-python`, and drops `run`/`docker-build`
from the Makefile surface. See stack.md's **Libraries** section for the full deltas.

- Migrate `setup.py` + per-extra `requirements-*.txt` to `[project]` + `[project.optional-dependencies]`
  (self-referential extras preserve a shared `-r` graph) + `[dependency-groups].dev`; add a
  `[build-system]` (hatchling or `uv_build`) and a `py.typed` marker.
- Keep `requires-python` a floor (`>=X.Y`) so consumers on older minors install; the tracked
  `uv.lock` resolves for that floor. Rewrite a packaging-contract test to read `pyproject.toml`
  via `tomllib` rather than execute `setup.py` (executing it needs `setuptools`, absent on 3.14).
- No PyPI publish for a git-tag-installed library: release with `make bump` + `make push-tag`;
  consumers install the tag. cz bump must carry `pre_bump_hooks = ["uv lock", "git add uv.lock"]`
  (stack.md §Versioning) — the library's own version is in `uv.lock`, so without it the `uv-lock`
  hook rewrites the lock mid-commit and aborts the bump. `PARITY` is reachable (unlike the monorepo case).
