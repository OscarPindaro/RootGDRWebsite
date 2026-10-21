# Python backend conventions

Team-specific service rules. [index](index.md) owns routing, [stack](stack.md) owns tooling,
[api](../api.md) owns the HTTP contract, and [async](async.md) owns everything outside the
request path. How far these rules reach on a given task is set by the
[development loop](../../development-loop.md)'s Standards gate.

Layout: `app/{api,config,log,model,repository,service,utils}` plus `exception_handlers.py`,
`middleware.py`, `lifespan.py`, and `main.py`. Agents live under `app/service/ai/` with their
prompts under `app/repository/ai/`; background work lives under `app/worker/`; Alembic revisions
live in `alembic/` beside `app/`.

Flow: API → Service → Repository → SQLAlchemy Core → PostgreSQL.

## Shape of a product

A product is one deployable application divided into modules, not a set of services. Split a part
out only when something forces it: it needs different hardware such as a GPU, it must scale on its
own, it must be released on its own schedule, or something outside the application must call it
directly. Never split because two things feel like different concerns. Keep a written checklist
for pulling a module out, so that separating one later is a planned job rather than an emergency.

For a capability several products need, **start with a library. Build a service only when the
capability needs shared state, shared policy, or shared metering.** That sentence settles most
arguments about whether something should be a service: a model gateway is a service because it
meters, logging is a library because it does not.

## Data store

Postgres everywhere. Keep document-like data in JSONB columns first, and take a separate document
database only when the write volume or the shape of the data genuinely defeats JSONB. The database
is always managed and always next to the application it serves: the hosting platform's own Postgres
at the velocity tier, RDS or Aurora inside our cloud account at the cloud tier — especially for
customer-facing or confidential work, because it stays on the private network with managed
credentials and point-in-time restore — and SQLite for a single-machine tool.

Decide at design time how one customer's data is separated from another's, and write it down. A
tenant column on each table is the default. Use a separate schema per customer when isolation or
deletion is a contractual promise. For data that changes over time, use an event log when the
domain is naturally a sequence of events and snapshots when tracking something outside our control.
Slowly-changing dimensions belong in the warehouse, not in the application database.

## Tenants and seams

Exactly one tenant is resolved per request, at the edge, before any handler runs. It comes from
the authenticated principal. Where a client legitimately selects among several tenants, that
selection is validated against the principal's entitlements before anything uses it — a tenant
the caller merely named is not a tenant the caller may read.

The resolved tenant travels in the typed principal object and is never re-read from the raw
request further in. Each endpoint declares the tenants it supports and rejects the rest. How the
tenant reaches the edge — header, path segment, token claim — is the project's choice.

One repository serves all tenants. Add a tenant service subclass only for unique orchestration,
and never create an empty subclass.

## Types and Pydantic

Every new or changed function and method is fully typed, including its return. Use precise built-in collections, unions, Enums, Literals, Protocols, or TypedDicts. Avoid `Any` except at an untyped external boundary, then validate or narrow it immediately.

Use Pydantic `BaseModel` for structured data that needs validation, serialization, or a schema, and `BaseSettings` for configuration. The same model then carries through request validation, agent output schemas, eval cases, and instrumentation — that one type system spanning four concerns is why the backend language is Python. Use a dataclass, TypedDict, or plain type for trusted internal data that needs no runtime validation; do not wrap simple scalars or temporary values in models.

When responses combine DB columns and computed/service fields:

- `*DbRow` contains exactly SELECT columns;
- `*Model(DbRow)` adds service and computed fields;
- query/filter builders accept only `*DbRow`;
- endpoints return `*Model`; `*Response` is only an envelope.

Pass the `*DbRow` type to anything that builds a statement, never the enriched model. Computed fields must never reach SQL.

Never reuse request models as responses or hide internal markers in `json_schema_extra`; it is public OpenAPI.

## Settings and lifespan

- Configuration is layered: base, then environment, then local. Secret *references* live in configuration and resolve at deploy time; secret *values* never do.
- Use cached `BaseSettings`; tests override dependencies or clear the cache. Secrets use `SecretStr`.
- Secrets arrive through one named resolution seam, so a cloud secret manager and platform-managed environment variables are both valid implementations of the same contract. Database credentials map exactly `host`, `port`, `dbname`, `username`, and `password`. Defaults exist only for local and test boot.
- Lifespan fetches real credentials with `get_secret_bounded`: 5 s connect, 10 s read, and 2 attempts. An unbounded secret read at boot turns a slow secret store into a failed deployment that looks like a hang.
- Anything meant to change while the service runs is not deploy-time configuration — see the four homes in [product](../product.md).
- A deploy prefix exists only where the platform in front of the service imposes one. At the cloud tier that is typically `/{env}/{service_name}`; at the velocity tier there is usually no prefix at all. It is empty locally either way. Do not invent a prefix the deployment does not require.

When a prefix does exist it has one owner. The team default puts `api_prefix` on routes,
docs, and OpenAPI without also setting FastAPI `root_path`. In a brownfield app
that already uses `root_path`, keep those paths unprefixed. Prove the complete
externally visible path with an ASGI request; route inspection alone misses doubled
prefixes.

Create long-lived resources once in lifespan. Initialize a slots `RuntimeResources` dataclass before any call can fail; its optional fields allow partial cleanup. Yield a typed `RuntimeServices` mapping for `request.state`.

Read state through a sentinel helper that tells a missing key from a value set to `None` and names the missing key.

Validate configuration before heavy I/O and fail boot. A green readiness probe followed by universal request failures is worse than a failed deployment. Catch `CancelledError` only to log and re-raise.

Which values belong in configuration at all, and which belong in flags or admin settings, is in
[product](../product.md).

## App and middleware

- Build middleware, exception handlers, and a newly built router inside `create_app()`. Rebuilding the router lets tests clear settings and create an app with new values.
- Keep `app = create_app()` at module scope. Gunicorn must not preload or initialize network clients in the master.
- Set the HTTP keep-alive above the load balancer idle timeout (gunicorn `keepalive` → uvicorn `timeout_keep_alive`, or `timeout_keep_alive` for direct uvicorn). A shorter keep-alive lets the worker close pooled connections the balancer still reuses → sporadic 502s. This applies wherever something in front of the service closes idle connections — a cloud load balancer, a platform router. Derive the default from that component's actual idle timeout plus a margin (e.g. idle 900s → keep-alive 960). <!-- TODO(circeus): record the shared ALB idle timeout once known. -->

Gunicorn-hosted ASGI services follow the shared
[runtime patterns](patterns/runtime-patterns.md). Every worker and overlapping
ECS task runs lifespan; audit background jobs before changing that topology.

Starlette middleware is LIFO, so the last one added is outermost. Declare
`MIDDLEWARE_STACK_OUTER_TO_INNER`, add in reverse, and lock the result with a test on
`app.user_middleware`.

The greenfield default outer-to-inner is GZip, CorrelationId, CORS, Auth, Request,
OutboundContext. The **required** part is the relative chain `CORS ⊃ Auth ⊃ Request ⊃ Outbound`,
plus GZip outside any middleware that captures a payload. Each constraint earns its place: CORS
outside Auth so a 401 still carries CORS headers; Request inside Auth so the audit context reaches
the access-log task; Outbound innermost so it snapshots the resolved principal. CORS uses a
wildcard origin **without** `allow_credentials` — never both together.

`CorrelationIdMiddleware` is required whenever the logging preset wires the `correlation_id`
filter. Filter and middleware land together; never strip the filter to work around a missing
middleware.

On a brownfield service, do not reorder the host's existing outer middlewares. Insert ours while
preserving the relative chain.

## Errors and I/O

- Raise HTTP-agnostic `ServiceError` subclasses, so services and repositories never import web types. One exception module maps domain errors and has a catch-all. Public detail is fixed text, never `str(exc)`; log the traceback.
- One handler renders a `ServiceError` as the RFC 9457 problem document the client receives; see the [API conventions](../api.md). The two are one path, not two choices — the fixed-detail rule above is what keeps an exception message out of that document.
- Statements are built with SQLAlchemy 2.0 typed Core. The ORM layer is not used: no session, no lazy loading, no identity map. asyncpg stays the driver (`postgresql+asyncpg://`).
- Raw SQL is allowed and expected in analytics paths and in measured hot spots. Keep it under `app/repository/query/`, the single home for statement text. Every value is a bound parameter; only trusted Enum-derived schema or table names may be interpolated into the statement text, because an identifier cannot be a bound parameter and a tenant-derived one is otherwise an injection path.
- Acquire connections per call. A repository returns validated Pydantic models, never raw rows. Cursors require a transaction.
- Schema is owned by Alembic from the first revision. Every change — additive, destructive, or data-moving — is a revision with a recorded applied state and a downgrade path. Review what `--autogenerate` produced before committing it; it detects shape, not intent.
- Wrap blocking SDKs in a lifespan-created adapter using `asyncio.to_thread`; tests mock the adapter.

## Connection poolers

The engine owns the pool. SQLAlchemy's reset-on-return issues a plain `rollback()` on the driver
connection, which is cheap and is *not* the multi-statement batch a proxy treats as a pinning
event — so adopting this stack removes a failure the previous raw-driver rules existed to prevent.
Change that behavior only through `pool_reset_on_return` and a `reset` event listener, never by
reaching past the engine. Verified against the SQLAlchemy 2.0 documentation.

The rules below are hygiene without a pooler in front of PostgreSQL and correctness with one.

**Poolers that pin a connection when session state is touched.** The connection stops being
shareable and the proxy's pooling stops working, silently. AWS RDS Proxy is the measured case: it
pins on the batch a raw asyncpg pool issues by default — `pg_advisory_unlock_all`, `CLOSE ALL`,
`UNLISTEN *`, `RESET ALL` — observed on asyncpg 0.31. The engine does not send that batch, so do
not reintroduce it through `pool_reset_on_return`. Anything added there runs on every release and
costs a round trip per request as well.

**Poolers in transaction mode.** The connection goes to another caller between transactions, so
session state and cached prepared statements do not survive. asyncpg numbers prepared statements
sequentially, which collides across callers. The documented answers are `NullPool`, a dynamic
`prepared_statement_name_func`, or `prepared_statement_cache_size=0`, with the pooler configured to
`DISCARD` on return. Confirm which the deployed pooler needs before relying on it.

A repository borrowing the request pool therefore must not use session-scoped operations: `SET`,
`set_config`, `RESET`, `DISCARD`, `LISTEN`, session advisory locks, prepared-statement lifecycle
commands, or temporary tables. Each needs a deliberately owned connection and a design review.
Transaction-scoped advisory locks are fine, because they end with their transaction.

Name a pool setting after what it does. `pool_recycle` bounds how long a connection may live;
an idle timeout is a different thing and neither is a maximum lifetime for an in-use connection.


## Auth

Identity is provider-agnostic by construction. The only integration contract is OIDC discovery
plus JWKS validation, so any issuer becomes configuration rather than architecture. The
[auth patterns](patterns/auth-patterns.md) hold the executable shape.

- The internal user id is our own, immutable, and the primary key. External identities are stored
  as `(issuer, subject)` links pointing at it, never as the key itself — otherwise the identity
  provider cannot be changed once real data exists.
- External claims are normalized into our own principal object at the boundary. Nothing past the
  boundary reads a raw token or a provider-shaped claim.
- One broker federates outward. Do not integrate each application with each issuer.
- Provisioning — directory sync, user lifecycle — is a separate concern from authentication and
  does not share its path.
- Auth settings derive client, tenant, and the shared gateway audience from the secret store.
- One shared gateway identity serves every backend behind the gateway; never create one per service.
- Create one M2M httpx client per target audience through the shared token provider. Enable it only when both secret and audience exist.
- Swagger wiring passes the deploy prefix (see [auth patterns](patterns/auth-patterns.md)).

## Integrations

A product-critical integration is coded, not improvised: a typed client, a rate-limit budget,
retries, and idempotency. Never reach a system through a direct connection that bypasses its
authenticated front door — legacy databases included. Every sync declares one source of truth and
carries a reconciliation job, because two systems that both believe they are authoritative will
eventually disagree and nobody will know which is right.

An incoming webhook verifies the signature before it trusts the body, handles a repeat safely,
tolerates a replay, and sends its failures to a separate queue that raises an alert.

Office automation belongs in a self-hosted workflow tool and may never hold logic the product
depends on. When the same kind of system has to be integrated across many portfolio companies,
evaluate a unified-API vendor before building one connector per company — that is a build-or-buy
question with a real answer either way, not a matter of principle.

Response format is part of the contract. One measured case: an upstream that omits null JSON
properties made a column that was null in every row disappear entirely from the result. Prefer a
schema-preserving read format such as Arrow when callers depend on stable columns, and normalize
missing values at the adapter boundary only when the public response needs another stable shape.

## Tests

Two levels, owned by directories:

- `tests/unit/` proves one rule or component, replacing its direct collaborators;
- `tests/integration/` proves several real components together through the public API.

Mark an integration test `live` when it needs a real external resource. `live` is an execution
requirement inside the integration level, not a third level: normal local and CI runs exclude it, and
developers select it manually. An explicitly selected live test must fail when its configuration or
infrastructure is missing — a skipped run reports success while proving nothing. Keep live checks
read-only. Set `asyncio_mode=auto` and run the default suite before every commit.

Anything crossing the database boundary is tested against a real PostgreSQL in a container, with
the Alembic revisions applied first. A test that only replays what we meant to send cannot catch
invalid SQL, a column that does not exist, a constraint that behaves differently than assumed, or
a migration that did not produce the schema the code expects — and those failures otherwise reach
production.

Protect against repeated queries with a statement counter that asserts how many statements an
operation issues, not by matching generated SQL strings. The statement text belongs to SQLAlchemy,
so asserting it tests the library's renderer and breaks on upgrades that change nothing.

Never mock a security-relevant boundary. Use an emulator that mints real signatures and tokens, so
the test exercises verification rather than a stub's willingness to agree.

Do not add snapshots, captured database exports, or replay pools — small explicit examples are
easier to review and to keep true.

Keep async pools, clients, and services on compatible pytest event loops;
function-scoped fixtures are the safe default. A FastAPI dependency override
must expose only typed parameters that FastAPI can resolve. An unused untyped
parameter is interpreted as request input and can turn a valid integration flow
into a false 422.

Tests of the global exception handler use `TestClient(..., raise_server_exceptions=False)`. Mock typed seams with `MagicMock(spec=...)` and async methods with `AsyncMock`. Clear dependency overrides after each test.

## Other conventions

- LLM work follows [LLM conventions](llm.md).
- Background work, queues, and cross-process coordination follow [async](async.md).
- Every new Python service follows [observability](observability.md); its base logging stack is mandatory and not optional at creation. For a service already on a different logging stack, converging it is a decision, not a defect: propose it with its cost and let the owner choose, and never report the existing stack as a finding on its own. Logfire is added or repaired through `integrate-observability` in either case.
- Extracted helpers use public names. Prefer pure Python collections for small data and generators for large data.
