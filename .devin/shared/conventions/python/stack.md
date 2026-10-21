# Python project stack

Team project files and gates; [backend](backend.md) owns application architecture.

## Hosting tier

Every service has a tier, written into its README when it is created, as a line reading `Hosting tier: velocity` or `Hosting tier: cloud`. A fixed form is what lets a check confirm it.

**Velocity tier — the default.** A platform host runs it.

**Cloud tier.** Cloud-direct containers, described as code and reproducible from the repository.
A workload belongs here when any one of these is true, and the README says which:

- a portfolio company or an external customer can reach it;
- it needs cloud primitives — private networking, fine-grained permissions, GPU;
- downtime has a contractual cost.

**Holding confidential data is not one of the reasons.** An internal tool can hold sensitive
material and still tolerate an outage. What that material needs is control over who reaches it and
over what leaves our systems, which [security](../security.md) owns and which applies wherever the
workload runs. Choosing the expensive tier for confidentiality buys nothing the security rules do
not already give.

Infrastructure as code follows the tier. The **velocity tier writes none**: the hosting platform's
own configuration, committed to the repository, already answers what is deployed, and writing more
than that is performed rigour. The **cloud tier uses OpenTofu**, which reads Terraform's files and
state, so moving either direction is a straight swap. It is chosen because its MPL licence matches our position on
using dependencies commercially, where Terraform's sits awkwardly, and because it encrypts its
state file natively, and state files hold connection strings. The cost is honest: the wider market
still says Terraform, so diverging buys a small amount of friction forever. Use Terraform when a
partner or vendor toolchain requires it; the state is compatible, so one engagement costs nothing
strategically.

Each environment gets its own cloud account from the start, because adding that boundary later is
painful. The cloud tier runs development, staging and production. The velocity tier runs production
plus a temporary environment per change.

Everything is containerized at both tiers, so moving tier is a configuration change rather than a
project. Which products count as cloud tier is a business call, revisited as the portfolio changes.

## Runtime and dependencies

- Pin one Python minor in `.python-version` and constrain it with `requires-python`. Pin the newest stable minor for which every required dependency publishes wheels — building from source on a runner is how a fast CI becomes a slow one. Record the pinned version in the project and revisit it at each annual release.
- `pyproject.toml` is source: runtime dependencies in `[project].dependencies`, tools in `[dependency-groups].dev`, and `[tool.uv] package = false` only for non-packages without project scripts.
- Runtime pins normally use minor wildcards; tools use major wildcards when compatible. Preserve existing pin shape.
- `uv.lock` is the only tracked lock. Use `uv lock`, `uv lock --upgrade`, `uv sync --locked`, and production `--no-dev`. Override broad lock ignores with `!uv.lock`.
- Remove requirements files and `VERSION` only after dependencies/version are represented, uv resolves, and all consumers migrate.
- Pin git dependencies to tags. Private git dependencies use SSH and an authorized agent, never embedded tokens. Keep Gunicorn pinned: an unbounded upgrade caused a production deploy hang.
- Gunicorn-hosted ASGI services declare the separate `uvicorn-worker` adapter
  and `uvloop`; do not use the deprecated bundled
  `uvicorn.workers.UvicornWorker`. Keep server values in the master-safe
  Pydantic model and executable shape defined by the
  [runtime patterns](patterns/runtime-patterns.md).
- Size workers from measured cloud CPU, memory, concurrency, latency,
  database-pool capacity, and failure behavior. Do not derive them from
  `(CPU * 2) + 1`.

## Quality

- **Ruff:** line length 100; select `E,W,F,I,N,UP,B,C4,SIM,ASYNC,S,DTZ,PT,LOG,G,RET,PTH,TID,FAST,RUF,PL`.
  - Derive the target from `requires-python`.
  - Ignore E501 because the formatter wraps lines.
  - Allow FastAPI factories for B008. Keep TC disabled when annotations are evaluated at runtime.
  - For existing code, use measured and documented ignores while fixing findings. Never reduce the selected rules.
- **mypy:** use the Pydantic plugin, precise annotations, stubs, and narrow ignores. New projects enable `disallow_untyped_defs` globally. Existing projects may enable it in stages through model → repository → service → API, but every new or changed function is fully typed. Set `python_version` to the pinned interpreter; pinning it below the interpreter makes mypy parse newer installed stubs (e.g. numpy) as the older version and abort.
- **import-linter:** enforce API → service → repository → model only when those layers exist; keep cross-cutting modules outside.
- **pytest:** the default selection excludes `live`, and the `live` marker is declared. A coverage floor never belongs in `addopts`: without `--cov` beside it, it is silently inert and measures nothing; with `--cov` beside it, `pytest tests/test_one.py` fails at the floor for running one file rather than for anything being wrong. A floor belongs in the Docker or CI command, where the whole suite runs. Integration tests that cross the database boundary run against a real PostgreSQL in a container, started once per session and migrated before the first test.
- **Coverage is measured and never gated.** Nothing in CI fails on the number: there is no minimum to reach and no rule that it may not drop. A fixed target gets met by tests that run lines without checking anything, and a limit that may only rise makes somebody write filler tests the first time a hard-to-test change dips the total — both teach the behaviour they exist to prevent. Read a low number as a reason to look, and let review catch an under-tested change, because a reviewer can see *which* part is untested and whether that matters. Never quote a coverage percentage as evidence of quality — it answers a different question than "are the fragile states covered". A project that keeps a floor anyway has deviated for its own reason and writes that reason down.
- Dev dependencies include commitizen, mypy, pip-audit, pre-commit, pytest, pytest-asyncio, pytest-cov, pytest-mock, pytest-randomly, and Ruff; add import-linter or stubs only when used. A service with a database adds the container fixtures its integration tests need.
- A service with a database declares SQLAlchemy and Alembic as runtime dependencies, with asyncpg as the driver. Declare SQLAlchemy as `sqlalchemy[asyncio]`: the extra brings greenlet, which every statement on an async engine needs. Without it the service builds, starts and answers its health check, then fails on the first query.

## Commands

The self-documented Makefile defaults to `help`. Required targets: `install`, `lock`, `upgrade`, `test`, `lint`, `cov`, `audit`, `run`, `bump`, `push-tag`, `clean`, `docker-build`; add others only for real capabilities. A Gunicorn service also exposes `run-dev` for the macOS-safe local runtime described in the [runtime patterns](patterns/runtime-patterns.md).

- `install` performs locked sync and installs pre-commit plus commit-msg hooks; alignment must run it.
- `lint` matches Docker: Ruff check/format, mypy, and optional import-linter.
- Docker/CI invoke uv/tools directly. Do not wrap a one-use obvious command.

## Pre-commit

- Chain basic checks and `check-added-large-files` (exclude only `uv.lock`), then uv-lock, local Ruff fix/format, local mypy, and conditional import-linter. Never use a top-level `exclude`: put necessary data or generated-file exclusions on individual hooks so the large-file guard still sees them. Add `zizmor` whenever `.github/workflows/` exists; commitizen runs on `commit-msg`.
- Do **not** set top-level `fail_fast: true`: it stops after the first failing hook, so the autofixers (whitespace, Ruff fix, Ruff format) never all run in one pass and each run surfaces only one problem. Leave it default; scope `fail_fast` per-hook if ever needed.
- Run Ruff as local `ruff-check` then `ruff-format`, after uv-lock. Entries use `uv run --frozen`, `--force-exclude`, `language: unsupported`, and `require_serial: true`; the checker also uses `--fix`. Do not use the `ruff-pre-commit` mirror: its `rev` is a second Ruff pin that can drift from `uv.lock`. Mypy and import-linter are local frozen hooks with the same language.
- Keep `uv-pre-commit` aligned with Docker/setup-uv (same uv version). Hold them equal with a Dependabot multi-ecosystem group (`uv-toolchain`) owning the Docker `astral-sh/uv` and pre-commit `astral-sh/uv-pre-commit` sources; a one-time revision edit passes today and drifts at the next Docker bump.

## Docker

- Every external `FROM` uses an explicit tag plus manifest digest; weekly Docker Dependabot updates it.
- Copy the binary from a pinned `ghcr.io/astral-sh/uv:<version>@sha256:<digest>` image, sync runtime with `--locked --no-dev --no-install-project`, add groups only in dev/lint/test, and copy `/app/.venv` into runtime. Never install uv with pip or install requirements files.
- `.dockerignore` excludes virtualenv, coverage, caches, reproducible output, and agent-instruction dirs (`.agents`, docs) only after checking stage inputs — `*.md` matches root-level files only, so a nested rules edit otherwise invalidates `COPY . .` and re-runs every in-build gate. Native Rust projects exclude local `target/` trees. Measure context before/after. Build native wheels in a dedicated builder and install them into the venv.
- Docker lint matches `make lint`; test stages measure coverage.
- The production command is the one typed runtime launcher, normally
  `python -m app.run_gunicorn`. Use `exec` inside it so Gunicorn receives
  container signals as PID 1. Inject the immutable image tag or revision as
  `CODE_VERSION`; do not report source HEAD as the deployed version.
- Test stages pin `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1`: numpy/pandas size BLAS pools on host cores and oversubscribe shared runners (measured 6 s local vs 69 s CI for one suite). Runtime stages stay unpinned.
- If CI disables a Dockerfile gate and runs the container instead, the effective command must preserve the same gate, including coverage measurement and the complete lint chain.
- Bake SSH forwarding requires `--allow=ssh` on Buildx ≥0.17.

## CI

Authenticate to a cloud with OIDC. No long-lived deploy credential exists in CI — a stored cloud key is valid until someone notices it leaked, while an OIDC token is minted per run and expires in minutes. Repositories call a shared reusable workflow rather than each carrying its own copy, so a pipeline defect is fixed once.

Every branch push runs lint, format, typing, applicable import boundaries, tests, coverage measurement, a security gate (dependency audit and workflow audit), and — for any repository whose code calls a model — the eval suite. A known advisory with no fix available is waived explicitly and in writing, never by removing the gate. A runner owns no real external resource, so CI never selects `live`: a `-m` argument replaces the project default, so any override must restate `not live`.

Choose one approach:

1. native orchestration for matrix, service, or sibling-repo checks Docker cannot express clearly;
2. one cache-only Bake validation;
3. one image-producing Bake pipeline when the checked image is deployed.

For persistent cache-only builders, reuse `check-python-bake.yml`. It:

- makes one Bake call with `output=["type=cacheonly"]`;
- avoids external caches and image loads;
- keeps builder state and hashes the full repository/runner scope;
- bounds worker storage with GC.

A replacement must keep all these properties. Do not add this mode to classic image-loading checks.

Classic image-loading checks run each effective gate once. Do not rebuild and rerun a gate already executed in Docker unless its replacement preserves the full contract.

Check and deploy workflows must not both handle the same protected-branch push. When replacing CI with a reusable workflow, pass non-default resource identities as inputs.

Two rules hold at any tier: never rebuild and retest a source tree that was already built and tested, and give each cache location exactly one writer. A platform host applies them with whatever cache it provides.

### Registry cache — cloud tier

Cache-only checks need no ECR repository. In image-producing Bake, each registry cache location has one `cache-to` writer. Other targets import that cache or use a different location: give lint/test their own suffixed locations (`cache-{branch}-lint/-test`) and read the `cache-dev*` pools as fallback so staging/main builds reuse what dev already validated.

In deploy pipelines, a push whose `HEAD^{tree}` equals the tree of an already built and tested `last-build-*` tag (typical dev→staging or staging→main merge) retags the existing ECR images server-side (`batch-get-image` + `put-image`) instead of rebuilding and re-testing — same trust model as a promote workflow, proven by tree equality. Measured effect on a real service: staging merge 15 min → 4.5 min.

### Supply chain

Pin every Dockerfile used by CI/release. Dependabot updates uv and Docker weekly, groups Python updates, and cannot update private git tags. For the Docker `python` image, ignore minor and major updates but allow patch updates. Give every updater `cooldown.default-days` of at least 7. Give the uv ecosystem `versioning-strategy: lockfile-only`, or its default rewrites the pyproject ranges (moving even an upper bound) to adopt the newest release, which is how a breaking major slips past a declared cap. `make audit` exports the lock while excluding unhashed private git packages.

Pin remote GitHub Actions `uses:` to a full commit SHA with a `# vX.Y.Z` comment (same trust model as the Docker tag+digest rule; zizmor's `unpinned-uses` requires it). The one exception is a team-owned shared-actions repository, which is also where the shared reusable workflow above lives. It is not yet named, so until it is, treat any concrete name in a project as the placeholder it is.
A team-owned shared-actions repository may stay on a centrally managed moving major compatibility channel (e.g. `@v2`), with `# zizmor: ignore[unpinned-uses] trusted team moving major` on each reference. A SHA with a `# v2` comment does not follow later tag movement. In the `github-actions` Dependabot block, give that repository's dependency name the setting `update-types: ["version-update:semver-major"]` so it cannot propose the next major. Do not extend this exception to another repository.

Do not rely on moving major tags for external actions — some publish moving majors only for older versions (e.g. `astral-sh/setup-uv` stops at `@v7`, so `@v8`/`@v9` never resolve and must be pinned by full version/SHA). Set `persist-credentials: false` on `actions/checkout` unless a later step needs the token. Dependabot's `github-actions` ecosystem bumps external action SHAs.

## Versioning

`[project].version` is the source. Commitizen uses `version_provider = "pep621"`, annotated tags, Conventional Commits, and changelog-on-bump. Use `version_files` only to synchronize a runtime constant that already exists.

Repos need a baseline version tag before inferred bumps. Push annotated tags with `--follow-tags`.

Anything published to a consumer follows semantic versioning, with exact pins before 1.0. Publishing is automated in CI and never done from a laptop — a release cut by hand is an artifact nobody can reproduce. State the deprecation policy when something is published, not when it is removed.

The project's own version is recorded in `uv.lock`, so `cz bump` changes the lock and the `uv-lock` pre-commit hook would rewrite it mid-commit and abort the bump. Regenerate and stage the lock before the bump commit with commitizen `pre_bump_hooks = ["uv lock", "git add uv.lock"]` in `[tool.commitizen]` (harmless when nothing changes; required for packaged libraries and any project whose root version appears in `uv.lock`).

## Libraries

A distributable library (consumed by other projects) follows the same
stack with these deltas — the preflight auto-detects it: a `[build-system]`, no
service `Dockerfile`, and not `package = false`.

- **Packaging:** declare a `[build-system]` (hatchling is the community default for pure-Python; `uv_build` is a valid uv-native alternative). Do **not** set `package = false` — the library *is* the package. Ship a `py.typed` marker (PEP 561).
- **Python:** `requires-python` is a floor (e.g. `>=3.11`), not a single-version pin, so consumers on older minors can install it; the tracked `uv.lock` resolves for that floor. `.python-version` still pins the dev interpreter. A floor carries an inline comment naming the feature that sets it — otherwise nobody can tell whether raising or lowering it is safe.
- **Extras vs groups:** user-facing optional features are `[project.optional-dependencies]` (shipped; names normalise per PEP 685); dev/test/docs tooling is `[dependency-groups]` (never shipped). Reproduce a shared requirements graph with self-referential extras (`aws = ["boto3", "pkg[dataframe]"]`).
- **Makefile:** omit the service-only `run` and `docker-build` targets.
- **No container:** the Docker invariants are N/A. A git-tag-installed library has no PyPI publish — releases are `make bump` + `make push-tag` and consumers install the tag (cz bump needs the `pre_bump_hooks` from §Versioning, since the library's version lives in `uv.lock`); a PyPI library adds a Trusted-Publishing (OIDC) release workflow instead.
- **CI:** a native `check*.yml` running Ruff, mypy, and pytest-with-coverage across the supported Python range is sufficient; there is no deploy workflow to keep disjoint.
- **`uv.lock`:** committed — it pins only the dev/CI environment, never consumers (only `[project]` version *ranges* propagate downstream).
- **Tell the consumers.** A package registry announces a new version; a git tag announces nothing, because nothing is listening. That job does not disappear when the registry is skipped — it moves to whoever cuts the release. **When a release fixes something a consumer is living with, update that consumer in the same piece of work.** This is written down because the gap is real: a consumer of our shared library sat one release behind, and the release it was missing repaired the link between its log lines and its traces. Nothing told anyone.

## Alignment

How far these rules reach on a given task is set by the [development loop](../../development-loop.md)'s Standards gate, which also owns the duty to offer adjacent convergence rather than doing it unasked.

`/align-stack` may align project-supporting files and apply safe mechanical fixes while preserving pins, entrypoints, runtime behavior, and unrelated work. Semantic or architectural changes need another approved plan. Never weaken a gate.

Completion requires preflight `PARITY`, executable host uv, successful `make install`, executable venv and both hooks, passing repository gates, and consistent Docker/CI. Report structural, installation, and application-quality states separately.
