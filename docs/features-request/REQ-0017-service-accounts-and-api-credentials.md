---
id: REQ-0017
requested_on: unknown
title: Service accounts and API credentials for bot clients
recorded_on: 2026-10-11
---

# Service accounts and API credentials for bot clients

## Request and motivation

Root GDR should be able to create **service accounts** — non-human identities
for bots — and issue each one credentials that an automated client can use to
call the application API directly. The intended client is an agent such as Devin
or Claude Code, and any future script, importer or scheduled job.

Today the only ways into the API are the interactive ones: password login,
Google SSO, and the development login. Every one of them belongs to a person and
produces a short-lived JWT pair (15-minute access, 30-day refresh). There is no
machine identity and no long-lived credential, so an automated client can only
work by impersonating a human account and riding that account's session.

The intended benefit: content work can be automated — the handwritten-draft
transcription of REQ-0016, bulk imports, migration or maintenance scripts — under
a distinct identity with its own lifecycle, instead of borrowing a person's
login.

This is feature intake, not implementation approval, prioritization, release
selection or an implementation-ticket plan. The credential mechanism below is
explicitly left open for a later decision.

## Current / desired behavior

**Current.** `src/backend/auth/` owns JWT issuance (`tokens.py`), the login and
refresh routes (`routes/auth.py`) and the request dependency
`get_current_user` (`dependencies.py`), which accepts `Authorization: Bearer
<access token>` or the `access_token` cookie. `UserModel` is the only principal
(`src/backend/users/models.py`): a name, a unique email, a role
(`admin`/`member`) and an `is_active` flag. Users come from invitations or
Google SSO; an admin can create one through `POST /users`, which takes only a
name and an email. Authorization beyond the role is world-scoped
(`src/backend/access/policy.py`, `WorldRole` master/player). There is no token
table, no credential management surface and no bot identity.

**Desired.** An admin creates a service account for a bot and obtains a
credential for it. The bot presents that credential to the existing API — for
example as `Authorization: Bearer <credential>` — and is treated as that
principal, subject to the same role and world-membership rules as any other
user. The credential is durable enough for an unattended client, can be listed,
rotated, revoked and given an expiry, and is shown once at creation and stored
hashed. The service account can be added to worlds so it can read and write the
content it is meant to manage, and the admin surface shows which accounts are
bots.

A concrete example of the desired workflow: an admin opens the admin surface,
creates a service account "devin-agent", copies the one-time credential into the
agent's private configuration, adds the account to a world as master, and the
agent then calls the world's content endpoints directly. Revoking the credential
later stops the agent without touching any human account.

## Scope and constraints

- **In scope:** admin-managed service accounts (a bot principal distinct from a
  person); durable API credentials usable as a bearer token against the existing
  JSON API; creation with a one-time display, listing, rotation and revocation;
  an expiry; hashed storage at rest; service-account membership in worlds
  through the existing role model; a way to tell a bot account from a person.
- **Explicitly deferred / to decide:** the credential mechanism itself —
  a long-lived opaque token (personal-access-token style) versus a
  client-id/client-secret pair with a token-exchange endpoint (OAuth2
  client-credentials style) — and whether both are needed.
- **Explicitly deferred / to decide:** a permission or scope model beyond the
  existing `UserRole` and `WorldRole` (per-endpoint scopes, read-only tokens,
  per-world restrictions).
- **Excluded from this request:** changing how human login works; open
  self-registration; any use of a development-only endpoint in production
  (REQ-0001 already forbids that).
- Project rules apply unchanged: credentials come from configuration or the
  database, are never committed or logged, and are stored hashed. Pydantic
  models at the boundaries; no `getattr`/`setattr`. `AGENTS.md`'s ban on
  dev-only auth endpoints in production stands.
- The consuming agents keep their credentials in private configuration outside
  the repository, as the board tooling already does with its token files.

## Acceptance criteria

Observable outcomes. Items marked *(proposal)* are inferred, not yet approved.

1. An admin can create a service account and receive a credential for it; the
   credential value is shown once and never retrievable again. *(proposal)*
2. A client holding that credential can call the existing API directly and be
   authenticated as the service account, with no browser, cookie or interactive
   login. *(proposal)*
3. A service account can be added to a world and then reads and writes content
   according to the same role rules as a human member. *(proposal)*
4. An admin can list the credentials of an account, revoke one, and rotate it;
   a revoked or expired credential is refused with a clean 401. *(proposal)*
5. Credentials are stored hashed, never logged, and never returned after
   creation. *(proposal)*
6. The admin surface distinguishes bot accounts from people and shows each
   account's credentials without exposing their values. *(proposal)*
7. Every service-account operation is admin-only. *(proposal)*

## References

- [The auth surface and the landing redirect](../features-implemented/auth-surface.md)
  — the current four login paths and their limits.
- [Admin and settings in the atlas system](../features-implemented/admin-settings.md)
  — where an account/credential management surface would live.
- [World access](../features-implemented/world-access.md) — the world role model
  a service account would reuse.
- `src/backend/auth/` — JWT issuance, login routes and `get_current_user`.
- `src/backend/users/` — the principal model and the admin user endpoints.
- `src/backend/access/policy.py` — the central access checks.
- [Handwritten draft transcription and content intake](REQ-0016-handwritten-draft-transcription-and-content-intake.md)
  — the first concrete agent client that would use a service account.
- [GitHub CI and manual deployment](REQ-0001-github-ci-and-manual-deployment.md)
  — production forbids development-only auth endpoints.
- [User guide](../user.md), [Database migrations](../database_migrations.md).

## Open questions

- **Credential mechanism:** a long-lived opaque bearer token, a
  client-id/client-secret pair with a token endpoint, or both? The request does
  not choose; this is the first decision to settle.
- **Permissions:** do service accounts reuse `UserRole`/`WorldRole` only, or is
  a scope model needed (read-only tokens, per-world limits, endpoint scopes)?
- **Roles:** can a service account be an admin, a world owner or a world master?
  Can it create worlds?
- **Identity and email:** what email (if any) a bot account carries, and whether
  it appears in the invitation and user lists or is filtered into its own
  section.
- **Credential lifetime:** default expiry, whether expiry is mandatory, and the
  rotation/overlap rule so a running agent can be rotated without downtime.
- **Multiple credentials:** one credential per account, or several with their
  own names and expiry.
- **Audit:** whether credential creation, use and revocation are recorded, and
  where.
- **Abuse limits:** rate limiting and any restriction on what a bot token can
  reach, given the credential is long-lived.
- **Client storage:** how the agent (Devin, Claude Code, a script) is expected
  to hold the credential — environment variable, private file, secret store —
  and how that is documented.

## Tracking

Initial intake key: `REQ-0017/T01`. Registered in Vikunja project **Root GDR**
(project ID **2**), task ID **10**; title, project and description confirmed by
read-back on 2026-10-11. Classified `type:feature`, `area:backend`,
`area:frontend`, `area:database` (colour `#2563EB`). No assignment, priority or
release is selected here. Current ticket state belongs in Vikunja.
