# Python observability conventions

Team contract for Python logging and telemetry. [backend](backend.md) owns the
service structure; [llm](llm.md) adds AI-specific behavior. Apply the concrete
[patterns](patterns/observability-patterns.md) instead of reconstructing them in each
skill.

**The contract is OpenTelemetry, using the GenAI semantic conventions where they apply.**
Instrument once; the backend stays swappable. The shared library already draws that line:
`circlex.observability` and `circlex.http` are backend-neutral, and `circlex.logfire` is the
adapter for the backend currently chosen. Point a different adapter at the same instrumentation
and nothing in the application changes.

Two things follow, and they are not negotiable. Never run two AI-observability platforms — the
second one costs money to disagree with the first. Never add vendor-specific instrumentation that
is not OpenTelemetry-shaped, because that is the part that cannot be pointed somewhere else later.

The shared library is `circlex-utils` (`github.com/Shop-Circle/circlex-utils`),
installed from a released git tag and taken by extra — `circlex.logging` for the
logging stack, `circlex.http` for instrumented outbound calls, `circlex.context`
for the audit context, `circlex.logfire` for the export adapter,
`circlex.observability` for header redaction and capture settings.
<!-- TODO(circeus): name the reference service; it does not exist yet. -->

The [TypeScript conventions](../typescript/observability.md) are the other half of this same
contract. They state what differs in a JavaScript runtime — bundlers rewriting imports,
processes exiting before batches flush — and link back here for the shared reasoning.

The workflow — discover, converge, prove — lives in `integrate-observability`. This file owns the facts.

Promote a recurring improvement here or into the shared library instead of copying it into
another skill.

## Ownership

Every new or refactored Python service has the base logging stack below. The export adapter is
optional; the base is not, and it must be established or repaired before an adapter is added.

The shared library owns reusable code. Shared conventions own stable team
decisions. The application owns service names, logger namespaces, feature maps,
business attributes, metrics, and resource composition. Vertical skills own
discovery, the approved merge, and proof; they link here instead of restating
these rules.

Until the shared library exposes a complete application bootstrap, keep the
small secret-state resolver, Logfire scrub callback, FastAPI request mapper,
and raw subprocess adapter in the application. Do not import unreleased library
source.

Two backends are approved: **Logfire by default, and Langfuse self-hosted when a project needs the
data to stay in our own account.** Instrument once through OpenTelemetry either way, so the backend
stays a deployment choice rather than a rewrite.

**One tracing project per product.** Service, environment, release and business unit are filters
inside it, never separate projects. Splitting by anything other than product cannot be undone
later, because the history stays split. The layout is the decision; the vendor is not.

**Keep everything for 14 days to start, then reduce.** While a system is new nobody knows which
records matter, so nothing is discarded early. That only works if the reduction actually happens,
so it has a trigger rather than an intention: review the policy once the first full month of real
volume is visible, and set per-kind fractions then. Errors and model calls stay at full volume
whatever else changes — they are both the expensive ones and the ones worth reading.

**Only alert on something that has a written response.** An alert nobody acts on is noise attached
to a pager, and it trains people to ignore the next one.

## Base logging

Use `circlex.logging`'s `standard_console_config` and `LoggingConfigBuilder` in
one project logging module. Apply that config at every entrypoint the project
actually supports: Gunicorn during worker-local app import before its first log
and again in `post_worker_init`, an existing programmatic Uvicorn entrypoint
through `log_config`, and workers or CLIs through
`logging.config.dictConfig`. Do not add another entrypoint only for logging.
Declare `python-json-logger` and `asgi-correlation-id` directly: the application
imports or configures both and must not rely on the library's transitive
environment.

Use `logging.getLogger(__name__)` and `%` placeholders. Configuration belongs at
the process entrypoint, not at each module import, so new code does not call a
per-module logger factory. The library's `get_logger` exists as a drop-in while
migrating a service that already has one — it attaches a fallback handler only
when nothing else configured the logger, which is a bridge, not the target shape.

The standard config includes:

- structured JSON outside debug mode;
- correlation ID, endpoint, request-data, and Gunicorn shutdown filters;
- console routing for the application namespace and required framework/library
  loggers;
- `uvicorn.access` as the canonical per-request record.

FastAPI services install `RequestMiddleware` with request and response body
capture left off. Import it from `circlex.logging.middleware`: it is not
re-exported at the package level, so `from circlex.logging import
RequestMiddleware` raises. Install `CorrelationIdMiddleware` and preserve the
outer-to-inner middleware order defined in [backend](backend.md). Credential
headers are redacted at capture. Add new captured headers through a narrow
allowlist, never `.*`.

## Export lifecycle

One cached application function configures Logfire once per worker process.
Configure before emitting logs, constructing instrumented clients, or serving
the first ASGI scope. Keep application settings, the shared library, AWS, and
Logfire out of the Gunicorn master. Use the master-safe launcher and worker-local hook in the
[runtime patterns](patterns/runtime-patterns.md); do not build
`logconfig_dict` at Gunicorn configuration module scope.

An application-owned resolver maps the write-token secret name to three explicit
states:

- **provisioning pending** — no secret name: do not call AWS and configure
  `send_to_logfire=False`; console logging and local telemetry proof still work;
- **live** — a secret name resolves to a non-empty `LOGFIRE_WRITE_TOKEN`: export
  is enabled;
- **misconfigured** — a secret name was declared but cannot be read or has the
  wrong shape: fail startup outside local/test rather than running silently dark.

Resolve the secret only after a secret name is present, and only through the
project's secret-resolution seam — the same one [backend](backend.md) defines,
so a cloud secret manager and platform-managed variables both satisfy it.
Whichever backs it, the read is bounded: explicit connect and read timeouts and
a finite retry count. The
[adapter](patterns/observability-patterns.md#bounded-secret-read) shows the
shape for a cloud secret manager. Local and test runs may explicitly stay dark
even when a developer could resolve the secret. Never use a fake token to
represent the pending state.

The administrator handoff contains the target telemetry project, service name,
environment, where the secret will live and under what identifier, whatever
access the service needs to read it, and this secret shape:

```json
{"LOGFIRE_WRITE_TOKEN": "<write-token>"}
```

Use `logfire/<service>/write` as the proposed secret name unless infrastructure
requires another path. <!-- TODO(circeus): name the shared Logfire project. -->
The token decides the destination, so other projects are valid. Developers receive
the secret identifier, never the raw token. Do not commit tokens or put them in
local env templates.

## Logging and instrumentation

When Logfire is selected, add one `LogfireLoggingHandler` beside console and
route the application namespace, `uvicorn.access`, `uvicorn.error`, `fastapi`,
and necessary shared-library diagnostics to both. Keep noisy libraries such as `httpx` at
`WARNING`. Do not add a second bootstrap or handler path during brownfield work.

Configure the client, build the FastAPI app, add middleware, exception handlers,
and routers, then instrument system metrics and FastAPI exactly once before the
first ASGI scope.

Use the shared library's combined helper, `init_logfire_system_metrics`. It takes the
request-attributes mapper, the captured request and response headers, the fields to sanitize, and
the paths to exclude, and it turns on system metrics and FastAPI instrumentation once. Do not
compose those calls by hand beside it: two instrumentation paths mean FastAPI is instrumented
twice, and the library owns this one.

Build long-lived outbound clients through the shared library and pass the
configured `logfire_client`. Keep `logfire_capture_headers=False`; the shared
allowlist and credential denylist provide the useful headers. Do not combine global
`instrument_httpx()` with per-client instrumentation.

Use explicit spans for meaningful background operations and queryable keyword
attributes for their inputs and outcomes. Logs alone do not create a useful
trace hierarchy.

## Sensitive data

What counts as sensitive, and what may leave our systems at all, is the
[security conventions](../security.md). This owns the mechanism.

Keep scrubbing enabled. An application scrub callback may exempt only
these exact canonical auth fields: `auth.result`, `auth.mode`, `auth.enforced`,
`auth.type`, `auth.subject`, `auth.display_name`, `auth.email`, `auth.roles`,
`auth.scopes`, `auth.audience`, `auth.issuer`, and `auth.app_id`. Match complete
attribute names, not an `auth.*` prefix. Never disable scrubbing for the whole
process. Raw JWTs, cookies, API keys, service tokens, and secret values must not
become log or span attributes.

FastAPI instrumentation records parsed endpoint values by default. Supply an
application `request_attributes_mapper` that drops valid argument values and
removes the `input` field from validation errors unless the target has an
approved narrower contract. Keep only the error location, type, and safe
message. Keep secrets and personal data out of URLs and parameterize SQL.

Request and response bodies remain off by default. Enabling either requires a
field-level data review, bounded payload size, and regression proof that
credentials and personal data cannot leave the process.

Official references: [getting started](https://pydantic.dev/docs/logfire/get-started/),
[FastAPI instrumentation](https://pydantic.dev/docs/logfire/integrations/web-frameworks/fastapi/),
[scrubbing](https://pydantic.dev/docs/logfire/instrument/scrubbing/),
[Gunicorn](https://pydantic.dev/docs/logfire/integrations/web-frameworks/gunicorn/),
and [testing instrumentation](https://pydantic.dev/docs/logfire/reference/testing/).

## Processes and workers

Gunicorn topology and PostgreSQL listener ownership follow the
[runtime contract and proof](patterns/runtime-patterns.md).

Thread and executor context normally follows OpenTelemetry instrumentation, but
verify the actual boundary. Use the shared library's Pool initializer for
`multiprocessing.Pool`. For raw subprocesses, an application adapter captures
the W3C carrier into a namespaced environment variable and attaches it in the
child after Logfire is configured. No carrier means the child starts a valid
root trace.

Keep process-specific feature tagging in the application composition root.
Generic queue or worker code accepts a span factory instead of importing
Logfire when that keeps the module reusable.

## Model calls and metrics

Model telemetry — the uniform fields, the attribution tags, and cost — is owned by
[llm](llm.md). This owns how it is emitted.

Instrument only libraries the application uses. Optional Anthropic and
PydanticAI instrumentation catches `RuntimeError` for a missing integration;
other configuration failures remain visible.

Model message attributes are not scrubbed by default. When prompts, completions, tool
arguments, or results may contain sensitive data, use
`instrument_pydantic_ai(include_content=False)` and the equivalent
content-disabled provider option. Keep timing, model metadata, token usage, and
cost. See [Logfire scrubbing](https://pydantic.dev/docs/logfire/instrument/scrubbing/#llm-and-ai-messages).

Business metrics and manual spans belong to the application. Use stable,
low-cardinality attributes and OpenTelemetry semantic names where they exist.

## Proof

Deterministic proof covers:

- logging config construction and all supported entrypoints;
- middleware order, body defaults, header redaction, and FastAPI mapper output;
- exactly one client/bootstrap and the expected handler routing;
- outbound spans and process-context propagation;
- `provisioning pending` without secret-store access or export;
- deployed failure for a declared unreadable or malformed secret;
- tests that cannot pollute a shared telemetry project.

Use the adapter's local test exporter for span and attribute assertions. Pytest stays
dark by default; live test telemetry is an explicit opt-in.

A **live** claim additionally needs a real application request and a backend
query proving exactly one `uvicorn.access` record and one FastAPI request span
with the same trace ID, expected service/environment, immutable deployed code
version, and any expected outbound/background children. Compare the access-log
attribute and resource-attribute keys with a recent staging record before
claiming schema parity. Without an
administrator-provisioned secret, report **ready — provisioning pending**, give
the handoff above, and do not claim upload was tested.
