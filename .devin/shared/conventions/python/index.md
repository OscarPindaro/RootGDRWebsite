# Python Convention Index

Python with FastAPI is the default backend. TypeScript is the right choice when we do not own the
runtime we ship into — an embedded host application, a library whose consumers are JavaScript, an
edge API. Any other use of a second language needs a forcing function written into the project.

The reason is one type system: the same Pydantic model carries through request validation, agent
output schemas, eval cases and instrumentation, and nothing else on offer spans those four.

Load only relevant standards:

- [backend.md](backend.md) — FastAPI, Pydantic, SQLAlchemy Core, service and repository layers, lifespan, identity, integrations, and test levels.
- [async.md](async.md) — queues, retries, dead-letter handling, third-party dependency failure and degradation, and cross-process coordination.
- [../product.md](../product.md) — the event schema, the four homes for a runtime setting, and flag hygiene. Language-neutral.
- [../security.md](../security.md) — confidential data, agent blast radius, secrets, personal data. Language-neutral.
- [../api.md](../api.md) — the HTTP contract: versioning, pagination, errors, and rate limits. Language-neutral.
- [observability.md](observability.md) — base logging (mandatory for a new service, a proposal for one already on another stack), optional Logfire, sensitive data, workers, provisioning, and proof.
- [patterns/auth-patterns.md](patterns/auth-patterns.md) — executable FastAPI auth, M2M, audit, and enforce patterns.
- [patterns/observability-patterns.md](patterns/observability-patterns.md) — executable logging, token, FastAPI, and process-boundary patterns.
- [patterns/runtime-patterns.md](patterns/runtime-patterns.md) — executable Gunicorn/Uvicorn process boundaries, deployed code identity, listener leadership, and production-like proof.
- [stack.md](stack.md) — Python version, uv/pyproject, quality tools, Makefile, pre-commit, Docker, CI, dependencies, releases, and stack alignment. Its **Libraries** section covers the deltas for distributable packages (build backend, floor `requires-python`, extras vs dependency-groups, no container).
- [llm.md](llm.md) — the model-call contract, framework selection, prompts, budgets, and model telemetry.
- [retrieval.md](retrieval.md) — choosing a retrieval architecture per corpus, and the RAG rules when it is one.

How far these rules reach on a given task is set by the [development loop](../../development-loop.md)'s Standards gate. Derive commands from the repository. Standard uv checks are frozen pytest, Ruff check/format, mypy, optional import-linter, and pre-commit on touched files.

## Standards of record

- Shared library: **`circlex-utils`** (`github.com/Shop-Circle/circlex-utils`) — owns structured logging, the per-request audit context, and instrumented outbound HTTP. Install from a released git tag, taking only the extras used. Consume it rather than copying it. It has no auth module yet, so auth stays project-owned for now.
- Reference service: *none yet* — a repository that defines service structure and quality gates. <!-- TODO(circeus): name it once it exists. -->

If a project differs from these rules, state the effect and how it will return to the team standard.
