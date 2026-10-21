# Python authentication patterns

Contents: the identity model · dependencies · settings/bootstrap · Swagger ·
middleware/app wiring · outbound M2M · env/tests · auth observability/enforce.

<!-- Executable snippets are added here as each is verified against a running
service; the contracts below are binding without them. Do not
fabricate untested code to fill a slot. -->

## The identity model

Identity is provider-agnostic by construction, so no identity provider has to be
chosen for this contract to hold. Any issuer — a workspace directory, an
enterprise directory, an acquired company's own — becomes configuration.

- **The integration contract is OIDC discovery plus JWKS validation, and nothing
  else.** No provider SDK, no provider-shaped user object, no bespoke token
  format. A new issuer is a discovery URL and an audience.
- **The internal user id is ours, immutable, and the primary key.** External
  identities are stored as `(issuer, subject)` links pointing at it. Using the
  provider's `sub` as the key makes the provider unchangeable the moment real
  data exists, and the migration out of that is a data migration of every
  foreign key in the system.
- **Claims are normalized into our own principal object at the boundary.**
  Past the boundary, nothing reads a raw token or a provider-shaped claim. The
  principal carries the internal user id, the resolved tenant, roles and scopes
  in our vocabulary.
- **One broker federates outward.** Applications integrate with the broker, not
  with each issuer. Per-application issuer integrations multiply by the number
  of applications times the number of issuers, and they drift.
- **Provisioning is separate from authentication.** Directory sync and user
  lifecycle do not share a path with token validation; conflating them means a
  provisioning outage becomes a login outage.

A person keeps their identity across an issuer change because the internal id
never moved. That is the whole purpose of the shape.

General logging and Logfire follow the shared
[observability contract](../observability.md);
do not reproduce that setup here.

## Dependencies

The shared library is **`circlex-utils`**. It exists and is released; pin a tag,
never a branch or a SHA.

```toml
dependencies = [
  # Inbound: OIDC discovery + JWKS validation, the principal, the three modes,
  # the public-path guard, the auth.* fields, and require_role/require_scope/
  # require_policy.
  "circlex-utils[auth] @ git+ssh://git@github.com/Shop-Circle/circlex-utils@0.5.0",
  # Outbound, and a separate extra on purpose: the caller half depends on httpx
  # alone, so a batch job that only mints tokens installs neither PyJWT nor
  # Starlette.
  "circlex-utils[m2m] @ git+ssh://git@github.com/Shop-Circle/circlex-utils@0.5.0",
]
```

**Tell it where your issuer puts roles.** `AUTH_ROLES_CLAIM` defaults to a flat
`roles` claim, which is Entra ID's spelling and almost nobody else's. Point it at
the wrong place and `Principal.roles` is empty, so every `require_role` below
denies every caller — a 403 and a warning, in every mode, since gates do not
consult the auth mode.

```bash
AUTH_ROLES_CLAIM=realm_access.roles                             # Keycloak, measured
AUTH_ROLES_CLAIM=realm_access.roles,resource_access.api.roles   # realm + client roles
```

Dotted for nesting, comma-separated for several, unioned in order. Cognito uses
`cognito:groups`, Okta `groups`, Auth0 a namespaced URI — confirm yours against
one real token, never against vendor documentation. The library's own documented
Keycloak marker was `clientId` until a real token showed it is `client_id`.

Rules that carry over regardless of the library:

- Pin the auth library to a tag. Private git dependencies install over SSH with
  an authorized agent, never embedded tokens.
- Pin `httpx` directly; declare `asgi-correlation-id` yourself when using its
  log filter or middleware — never rely on a library's transitive environment.
  Missing it breaks `dictConfig` at boot.
- A caller-only target (mints M2M tokens, never validates inbound JWTs) installs
  a slim client extra instead of the full server stack. For Lambda, build a
  Linux layer in Docker with SSH agent forwarding.
- After a library upgrade, diff the lock and explicitly declare any direct use
  of packages the library stopped providing transitively.

## Settings fields

Nest the library's `AuthSettings` (or equivalent) as a field with its own env
prefix, never as an environment-mutating property — and do not redeclare its
env vars on your own Settings. Standard additions:

- one caller-credential secret name field; empty means auth off in local/test;
- one `*_M2M_AUDIENCE` field per outbound target; empty means no bearer;
- `api_prefix` as a computed field: empty locally, `/{env}/{service}` deployed.

`get_settings()` may be `lru_cache`d; drop the cache if tests monkeypatch
Settings.

## Bootstrap (at the app-creation site)

Resolve auth settings from the secret store only when a caller secret name is
configured; otherwise fall back to the plain settings object so local/test runs
keep auth off. A missing optional tooling secret uses a fallback; any other
secret-store error fails boot. Never fake a token to represent a pending state.

## Swagger

Pass the deploy prefix into the OAuth redirect URL wiring and lock it with a
redirect regression test — an unprefixed `docs/oauth2-redirect` is rejected by
the IdP. Rendering the Authorize button does not prove pre-authorization,
scope, or redirect URI. If FastAPI already has app-level dependencies, merge
them instead of letting a keyword splat replace them.

## Middleware stack — auth-specific notes

[backend](../backend.md) owns the ordering contract, the required relative chain, and the reason
behind each constraint. What auth adds:

Public-path exemptions: the documentation routes, `openapi.json` and the health path must be
exempt from auth, or load-balancer probes 401-loop once enforcement is on. Compare the actual
load-balancer health path against the exempted list and add the exact nested path when they
differ. Guard empty-prefix entries: an empty string in a `startswith`-based exemption list makes
**every** path public.

**GZip + streaming.** Search for `StreamingResponse`/`text/event-stream` before
adding GZip. Starlette excludes SSE from compression; lock this by asserting an
SSE response has no `Content-Encoding: gzip` so upgrades cannot begin buffering
streams silently.

## App composition

Compose at the target's existing app-creation site: one `create_app()` at
module scope so Gunicorn workers import it after fork; the target's existing
middleware-wiring function owns the exact chain; do not create a second app or
middleware path. Route the auth library's logger through the base logging
handlers so verifier diagnostics remain visible.

## `/me` + `/health`

`/health` stays public and returns a fixed body. `/me` is the canonical
end-to-end identity check: it requires an authenticated principal (401 when
anonymous, any mode) and returns subject, auth type, roles, scopes, audience,
issuer, app id, and email. Business routes are NOT individually gated while the
service runs in audit mode — the auth middleware is the global gate.

## Outbound M2M (only if the service calls other internal backends)

Keep token-provider construction in one factory module (`config/m2m.py`-style):
one cached provider, a `get_m2m_token(audience)` helper, and one client factory
per audience. `circlex.m2m.M2MTokenProvider` is that provider —
`provider.bearer_factory(audience)` feeds `make_outbound_async_client`, caches a
token per audience, refreshes before expiry, and collapses concurrent refreshes
into one request. It yields no `Authorization` header at all when either the
secret or the audience is empty, which is the byte-for-byte pre-auth path below. The bearer factory is built only when both the caller secret AND
the audience are non-empty (else no M2M header — the byte-for-byte pre-auth
path). Build one client per audience at startup, inject it into the consuming
service, and `aclose()` each at lifespan teardown so in-flight requests drain —
close clients before any DB pool.

**Downstream authz is on the calling service (M2M), not the end user.**
Backend→backend calls present the calling service's own client-credentials
identity; the downstream backend authorizes on the *service's* roles. The user
is authorized at the **entry** backend; deeper hops are service-to-service, and
the user travels downstream only as an audit breadcrumb header. This survives
the audit→enforce cutover: only the calling service needs the downstream grant,
not every user.

Do **not** forward the user JWT verbatim across hops: verbatim passthrough
requires disabling per-backend audience validation and defaults to fail-open at
the estate boundary. If a future requirement genuinely needs the *user's*
identity to authorize at hop 2+, use RFC 8693 token exchange / On-Behalf-Of
(audience-preserving, per-backend), designed deliberately.

**M2M authentication and app-role authorization are separate.** The middleware
validates the token and audience; it does not reject a principal for missing
roles. Role grants live in infrastructure; a route that requires a role must
attach a `require_role`/`require_policy` dependency — only that dependency
returns 403. The grant is infra, while the route gate is app code.

`circlex.auth` ships these as `require_scope`, `require_all_scopes`,
`require_role` and `require_policy`. They are plain callables taking a Starlette
`Request`, so FastAPI injects them by annotation and no FastAPI import is
involved. They refuse an unauthenticated request too — a gate states that a route
needs something, and "nobody" never has it — which is what lets one route enforce
while the service is still in `audit`.

## env-config / secrets-config (per env)

<!-- TODO(circeus): document the audience URI scheme and secret paths once the
IdP exists. Portable rules: -->

- The audience env token is the full environment word (`dev`/`staging`/`prod`,
  never an abbreviation) and must match the identifier registered at the IdP
  verbatim — a mismatched audience resolves to nothing and every token minted
  against it fails: silently in audit, as 401 under enforce.
- An outbound target's audience uses the env that target is actually DEPLOYED
  in, which may differ from this service's env. A target deployed in fewer
  environments than the caller needs an explicit collapse rule (e.g. staging
  callers use the dev audience) applied consistently in host and audience.
- Keep public identifiers (audiences) in env-config, not secrets-config; keep
  raw credentials only in the secret store.
- With an inbound API variant + an outbound-only batch variant, inbound keys
  (auth mode, own audience) go ONLY on the API variants; batch variants carry
  just the caller secret + outbound audiences.

## Tests (`tests/unit/test_auth_wiring.py`)

Assert: middleware order (CORS outside Auth outside Request outside
OutboundContext) and both auth middlewares registered; Settings nests
AuthSettings; the default auth mode is `off` (delete the ambient env var in the
test first — settings read it); the JWT verifier is `None` when IdP config is
absent; Swagger kwargs are empty for a bare AuthSettings and non-empty once the
tooling client is set; `/me` registered.

For each outbound M2M client, also assert the auth contract: a client built
with a bearer factory wraps it in the outbound-auth type; a client built with
neither factory nor audience attaches **no** `Authorization` header; the bearer
is attached when caller secret + audience are set; and any env-collapse rule
matches between host and audience.

Place the file where the project's runner collects it. Any env-config lint must
`pytest.skip` when `env-config/` is absent — `.dockerignore` excludes it from
the image, so a hard assert breaks the Docker test stage.

## Observability — `auth.*` span fields (Logfire)

The auth middleware enriches the **inbound** request span with the canonical
`auth.*` attributes on every request, even anonymous ones (the exact exemptable
field list lives in [the observability contract](../observability.md#sensitive-data)):
`auth.result` (`anonymous` · `success` · `invalid_token` · `expired`),
`auth.mode` (`off` · `audit` · `enforce`), `auth.enforced`, `auth.type`
(`null` · `user` · `service` · `dev`), `auth.subject`, `auth.app_id`,
`auth.display_name`/`auth.email`, `auth.roles`/`auth.scopes` (JSON arrays),
`auth.audience`, `auth.issuer`.

Tell `user` from `service` by `auth.type` — the only discriminator that holds
across an estate. `auth.app_id` is audit-only: never a caller-kind
discriminator and never an authz key.

Outbound httpx client spans carry no `auth.*`; propagated identity appears as
`http.request.header.*` (`traceparent`, caller service, env, request id, user
id) with `Authorization` redacted. Correlate inbound → outbound by trace id.

The per-request `uvicorn.access` record is the ground truth that logging and
auth observability meet: it is a stdlib-logging child of the FastAPI request
span and carries request/response fields, correlation ID, and `auth.*`. If it
is missing, the logger is not routed to Logfire or a noise filter dropped it.

Useful Logfire queries:

```sql
-- access record: empty means logging is broken
SELECT span_name, attributes->>'http.response.code', attributes->>'auth.result'
FROM records
WHERE service_name = '<service>'
  AND attributes->>'logfire.logger_name' = 'uvicorn.access'
ORDER BY start_timestamp DESC LIMIT 5;

-- auth cases before enforce
SELECT attributes->>'auth.result' AS result,
       attributes->>'auth.type' AS type,
       count(*) AS n
FROM records
WHERE attributes->>'auth.result' IS NOT NULL
  AND start_timestamp >= now() - interval '1 day'
GROUP BY 1, 2 ORDER BY n DESC;

-- requests that enforce would reject
SELECT url_path, count(*) AS n
FROM records
WHERE attributes->>'auth.result' IN ('anonymous', 'invalid_token', 'expired')
  AND start_timestamp >= now() - interval '1 day'
GROUP BY 1 ORDER BY n DESC;
```

## Enforce flip + role/scope gating (separate step after audit is verified)

Do NOT do this during the initial integration; it is for when the service moves
to user-facing enforcement. The staged rollout is the point of audit mode:

1. Run in `audit` until the observability queries show the
   `anonymous`/`invalid_token`/`expired` rate on real endpoints is ~0 and real
   user tokens classify as `user`.
2. Flip per env through configuration only (`AUTH_MODE: enforce` + task
   restart) — no code change and no env identity change. Verify the auth
   library version supports a config-only flip before scheduling it.
3. Effect: missing/invalid/wrong-audience/expired → 401; a `require_scope`,
   `require_role`, or `require_policy` dependency returns 403 when its
   requirement is absent. Per-route gates work in any mode, so one route can
   enforce while the service stays in audit.
