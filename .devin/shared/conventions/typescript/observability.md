# TypeScript observability conventions

**The contract is OpenTelemetry.** Instrument once; the backend stays swappable. The rules below
are the TypeScript half of the same contract the [Python conventions](../python/observability.md)
state — read that one for the shared reasoning, and this one for what differs in a JavaScript
runtime, which is a great deal: bundlers rewrite imports, processes exit before batches flush, and
a signal-killed server lies to a smoke test.

Never run two AI-observability platforms, and never add vendor-specific instrumentation that is
not OpenTelemetry-shaped.

The workflow — discover, converge, prove — lives in `integrate-observability`. This file owns the facts.

<!-- TODO(circeus): a shared observability wrapper library should own the executable
setup for TypeScript, as `circlex-utils` does for Python. It does not exist yet. -->

## Setup

Configure once per server process through one side-effectful configure entry
(`configureLogfire` in a subpath module — never the package root). Next.js:
from `instrumentation.ts` `register()` under a
`process.env.NEXT_RUNTIME === "nodejs"` guard, before boot migrations so they
land inside the trace; plain Node: at the entrypoint. The app mirrors the
library's split: one side-effectful configure module imported only by the
entrypoint, one pure log-helpers module for app code.

Logfire's own Next.js page recommends `@vercel/otel` + OTLP env vars instead.
Do not follow it: that path drops the wrapper's credential-header floor, region
pin, and shared logger, and the two cannot coexist (both register the global
tracer provider). Next.js's own docs bless a manual Node SDK in
`instrumentation.ts`, which is what the configure entry builds.

## No console bridge

Python's `LogfireLoggingHandler` routes existing log records into Logfire. The
JS SDK has no equivalent: `console.*` reaches stdout only, so configuring the
SDK does not make an existing console line queryable — the call site must
change. A line that must survive an unconfigured SDK (an audit trail) writes to
both sinks deliberately: console for CloudWatch (the only sink when no token is
wired), the wrapper's `logger` for Logfire (no-ops until configured). Do not
"deduplicate" the console write.

## Export lifecycle — two states, not three

Python distinguishes a third state, **misconfigured** — a declared secret that cannot be read —
and fails startup on it rather than running dark. Here the deploy platform resolves the reference
and injects the value, so a reference it cannot resolve fails the task before application code
runs: the unreadable case is caught earlier, not ignored. The one variant the application can still
see is a value that arrives present but empty or blank, and that fails startup too, for the same
reason — a service reporting healthy while exporting nothing is worse than one that will not start.
Everything else reduces to two states:

- **live** — `LOGFIRE_TOKEN` set: export on;
- **dark / provisioning pending** — unset: pass
  `sendToLogfire: "if-token-present"` so instrumentation is configured with
  export off. Never hand-roll a guard around the library, and never fake a
  token. With the option omitted, the configure call throws on a missing token —
  correct for a service that must export. One SDK caveat: a local `.logfire`
  credentials file (Logfire CLI) also counts as a token; `sendToLogfire: false`
  is the hard-off. Ignore `.logfire/` in git and Docker: it holds a live write
  token for a shared project. Wrap the configure call as well. With no token set
  the configure call reads that file and throws on a corrupt one, and Next.js
  rethrows from `register()`, so the local step that writes it can stop the
  whole server. Rethrow the wrapper's missing-token error and log the rest, or
  the same guard hides the missing token a service that must export has to
  fail on.

That guarantee covers a reference the platform cannot resolve, not a secret that
resolves to an empty value — plausible, since an administrator creates the secret
by hand before the token exists. `LOGFIRE_TOKEN=""` is falsy, so the service
deploys green and runs dark with nothing reporting it. A blank token can be
worse than an empty one: a resolver that returns `true` for `"   "` builds real
exporters and POSTs every batch with a garbage credential, while your own check
calls the process dark. The wrapper must trim both the `token` option and
`LOGFIRE_TOKEN`, so a blank value resolves to absent and the policy you named
decides it: `if-token-present` configures dark, the default throws. Trim in
your own check as well, or it reports live while the library runs dark. A
deployed process with `ENV` or `LOGFIRE_TOKEN` missing or empty must fail
startup or log an error; test for it with `NODE_ENV === "production"`, since
`ENV` is itself one of the values that may be absent. Declare
`NODE_ENV=production` in the image — Next.js sets it for its own standalone
server, but a plain Node process gets it from nowhere, and a deploy action that
replaces the task's whole environment block can otherwise let a worker reach the
configure call with neither variable while the check silently passes. A local
production build matches the same test, so prefer the error-log branch and keep
failing startup for a service that must export. The check reports the state and
then still passes the token to `sendToLogfire: "if-token-present"`, which is why
it is not the hand-rolled guard forbidden above: it never decides export on the
library's behalf. A token that is present but wrong cannot be caught at startup
at all — only the Logfire query in Proof finds that one.

## Identity — nothing is automatic

- `environment`: pass `process.env.ENV` (the same key the Python services use)
  unmodified — never a literal fallback, which would label a deployed record
  with it. `NODE_ENV` cannot tell environments apart (`production` everywhere
  deployed), so `ENV` is required wherever the service is deployed and the
  startup check above enforces it. Unset, it omits
  `deployment.environment.name` rather than faking one — the SDK drops null
  resource attributes — so records go unlabelled and an environment-filtered
  query misses them. The wrapper reads no variable itself
  (`environment?: string`, forwarded untouched), so it owns the option and the
  no-fallback discipline while the variable name is this contract's.
- `serviceVersion` + `codeSource` (`{repository, revision}` → Logfire's source
  links): the git SHA, injected as a Docker build arg (`APP_VERSION`), set as
  the last runtime layer so it never invalidates cached layers, passed from
  the workflow (`APP_VERSION=${{ github.sha }}`). Env-agnostic — images stay
  promotable.

## Sensitive data

OpenTelemetry JS has no capture-time header redaction (unlike OTel Python), so
the wrapper strips credential headers from the capture allow-list instead:
its capture-config builder allow-lists `x-request-id`, and the credential floor
(`authorization`, `cookie`, …) is un-removable — adding a credential header to
the allow-list cannot re-open the leak. Nothing scrubs a captured attribute, so
that strip is the whole protection for header capture. Scrubbing covers the two
paths that emit records, and each has its own configure call: `configure` covers
what `@pydantic/logfire-node` emits, and `configureLogfireApi` covers `logger`,
which runs on `@pydantic/logfire-api`. `@pydantic/logfire-node` holds no scrubber
of its own — it forwards the config to `logfire`, the package it does depend on.
`logfire` and `@pydantic/logfire-api` are published from one source directory
(`packages/logfire-api`) at different versions, each scrubbing in its own module
scope. OpenTelemetry's provider registry lives on `globalThis`, so duplicate
copies share it (§ Bundlers); a scrubber does not, so configuring one leaves the
other on Logfire's defaults.

A wrapper that configures only one scrubber has a live gap on the `logger`
path, and not only for custom entries. Logfire's defaults happen to cover five
of six typical floor names: `auth` matches `authorization` and
`proxy-authorization`, `cookie` matches `cookie` and `set-cookie`, and
`api[._ -]?key` matches `x-api-key`. Nothing matches `x-service-token`, because
the default set holds no pattern for `token` in any form. A service that passed
that header value to `logger` would send it to Logfire in plaintext. The wrapper
must configure both scrubbers with the same union, on one condition: import the
wrapper's logfire subpath and the package root in the same module format. A
package that ships both an ESM and a CommonJS build carries its own scrubber per
copy, so mixing the two leaves `logger` on the defaults with nothing to say so.
If such a gap was ever live, audit the records already written, because closing
the gap does not clean up after it. Keep scrubbing enabled; raw JWTs, cookies
and secret values must never become attributes.

The scrubber matches its patterns against attribute **values** as well as names.
Its 16 defaults are ordinary words where audit records get written —
`auth(?!ors?\b)`, `session`, `secret`, `csrf`, `ssn`, `credit[._ -]?card` and
more. The pattern array in `@pydantic/logfire-api` is the authority, so read it
rather than this sample. An outcome value `unauthenticated` arrives as
`[Scrubbed due to 'auth']`, so nobody can read it. Check both halves when you add
an attribute or an enum value, and guard a fixed value set with a test that runs
the real scrubber.

A denylist protects an attribute, never message text. A value interpolated
through Logfire's `{key}` templating reaches the scrubber as a bare string with
no name attached, so only its own text can match a pattern, and a credential
rarely does. `logger.info("peer {x-service-token}", { "x-service-token": tok })`
writes the raw value into the message even when the attribute itself is
redacted. Keep credentials out of message text.

## Bundlers

OTel patches modules via `require-in-the-middle`, which cannot patch code a
bundler inlined, so externalize the SDK — Next.js:
`serverExternalPackages: ["@pydantic/logfire-node"]`. That single entry is
enough: measured in a production Next.js app, spans from Next.js, `pg`,
better-auth and the app's own logger all export with it alone, because
OpenTelemetry keeps its provider registry on `globalThis` and duplicate bundled
copies therefore still share it. Do not widen the list on the theory that a
bundled `logfire-api` or wrapper library is a second, unconfigured instance —
that was tried and disproved. Check the standalone traced the package with
`find .next/standalone/node_modules -maxdepth 3 -type d \( -name "logfire*" -o -name "@pydantic" \)`.
Where the real files sit depends on the linker, so a `.pnpm` path alone calls a
healthy build broken.

The Node SDK cannot run on the Edge runtime; guard and keep imports dynamic.

## A signal-killed server drops its last batch — and it makes smoke tests lie

Spans are batched (default ~5 s), and a framework that owns `SIGTERM` (Next.js
does) exits from its own cleanup before the SDK's exit flush runs, so everything
queued dies with the process. Verified as a controlled pair in production:
identical build and requests, killed ~2-3 s later ⇒ nothing in Logfire even
25 s on; kept alive ~20 s ⇒ the full trace. An unhandled promise rejection
still gets through — that listener suppresses the crash, so the process stays
alive long enough for its flush to finish — so a setup in this state shows one
lonely error record and reads as half-working.

Set `OTEL_BSP_SCHEDULE_DELAY` (a measured good value is `2000`) to cap the
loss. This is not a preference: OTel Python registers an `atexit` flush and a
Gunicorn worker exits the interpreter normally, so Python services on the 5 s
default lose nothing. A Node service that skips this is the only one in the
estate dropping spans on every deploy, by accident rather than design. Measured
as a controlled pair: identical request killed 3 s later, `2000` exported every
record, the default exported none. For a smoke test, use it or keep the target
alive past the batch delay.

## Packaging

`@pydantic/logfire-node` should be an optional peer of the wrapper — declare it
and `@opentelemetry/api` as direct app dependencies (exact pins); its own ~15
required OTel peers auto-install, but verify they landed (a missing one fails
at runtime, not install). `protobufjs` needs a pnpm `allowBuilds` approval.

## Short-lived processes

A server never flushes manually, and a worker, CLI or seed script mostly doesn't
either: the SDK registers `beforeExit`, `SIGTERM`, `uncaughtExceptionMonitor` and
`unhandledRejection`, flushing on a 3-second budget, so an ordinary exit exports.
Three paths still need you. Ctrl-C (`SIGINT`) and a `process.exit()` of your own
escape the hooks entirely, and both also skip `finally`, so a `finally` alone —
the obvious fix — misses exactly the cases that need one. A genuinely uncaught
throw is best-effort at most: `uncaughtExceptionMonitor` observes without
preventing termination, and its flush is not awaited. So use all three of
`await shutdown({ timeoutMillis })` (re-exported by the wrapper) in a
`finally`, which covers a caught or rethrown error with a timeout you control; a
`SIGINT` handler that shuts down before exiting; and a shutdown before any
explicit `process.exit()`.

## Provisioning handoff

Follow [the Python contract's handoff](../python/observability.md#export-lifecycle),
including its secret shape. Two differences matter here.

The app's variable and the secret's key have different names, and nothing warns
you: the app reads `LOGFIRE_TOKEN`, the JSON key is `LOGFIRE_WRITE_TOKEN`. So the
container variable is `LOGFIRE_TOKEN`, and its secret reference ends in the JSON
key — the two trailing colons are the empty version-stage and version-id slots:

```yaml
LOGFIRE_TOKEN: "arn:aws:secretsmanager:<REGION>:<AWS_ACCOUNT_ID>:secret:logfire/<service>/write-<suffix>:LOGFIRE_WRITE_TOKEN::"
```

Name the container variable after the JSON key instead and the service boots dark
with a provisioned token sitting unread. Read the key from the secret; never
infer it.

The token is normally one secret shared by all environments (tagged
`environment: shared`) — the `environment` field carries the separation, so a
missing `ENV` is what breaks queries, not a wrong token.

## Proof

Deterministic (mock the configure call / the wrapper's `logger`, except the
scrubbing check): the dark path configures without throwing; a malformed
credentials file does not stop startup; `x-service-token` passed to the **real**
`logger` reaches an in-memory exporter scrubbed; the live path passes service
name, `ENV`-derived environment, version/`codeSource`,
`sendToLogfire: "if-token-present"`; a deployed process missing `ENV` or
`LOGFIRE_TOKEN` fails startup or logs an error; the capture allow-list excludes
`authorization`/`cookie`; two-sink helpers write the same attributes to both
sinks; entrypoint order (telemetry before migrations).

Choose the scrubbing name carefully: it must be one Logfire's defaults do not
cover, which among the floor names means `x-service-token` alone. Mock `logger`,
or pick `authorization`, and the check passes with the second configure call
missing — which is how this gap once survived a green suite in a wrapper
library itself.

A **live** claim needs a real request against a token-bearing process and a
Logfire query showing one request span and one audit record sharing a trace
ID, the expected service/environment/revision, and no credential attribute
anywhere. Console output and "no exporter errors" prove the code ran, never that
Logfire received anything — a first live claim once rested on exactly that
and was wrong. Without Logfire read access, say exactly which live evidence
remains unverified, and treat the integration as unproven until someone queries
it.
