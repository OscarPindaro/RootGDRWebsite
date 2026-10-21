# Security, privacy and governance

In any language. Ordered by threat model, not by anxiety: the first section is the one most likely
to hurt us, and each is worth doing before the next. How far these rules reach on a given task is
set by the [development loop](../development-loop.md)'s Standards gate — except that security
rules have no rungs. They bind on every line written, at every rung.

## 1. Where confidential data may go

Classify what may leave our systems, in writing, before the question is urgent. A class that has
never been written down is decided by whoever is in a hurry.

Confidential material is not sent to a third-party parser or model for convenience. When a
workload must not leave our account, its tooling — including observability and evaluation — is
self-hosted for that workload.

One redaction vocabulary applies everywhere the data can surface: logs, traces, prompts, and
anything ingested. The Python [observability conventions](python/observability.md) own the
mechanism — what is scrubbed, what may be exempted, and how model messages are handled. Redaction defined separately per surface leaks through the surface nobody
remembered.

## 2. What an agent is allowed to do

An agent's blast radius is a design decision, not a consequence.

- **Prompt instructions are never an access-control mechanism.** Text asking a model not to do
  something is a preference, and anything reaching the model can argue with it. Enforce at the
  boundary that actually holds — the token, the permission, the tool that is absent.
- Each agent gets a distinct machine identity with least privilege. Shared credentials make an
  audit trail unable to answer who did it.
- An irreversible action needs human approval: deleting data, sending something outward, moving
  money, changing access.
- Every action an agent takes is attributable to that identity and kept.

**Put an identity-aware proxy in front of a private service, so reaching it follows company
sign-on.** That half binds on both tiers. No SSH into a running service in our own cloud account. Operators reach it through a managed
access path that records who connected and when. On a hosting platform there is no server to
connect to and the rule does not arise. At either tier, a private service is never published with
only a password in front of it.

## 3. Secrets

The secret manager at the cloud tier, platform-managed variables at the velocity tier, reached
through one resolution seam so the application does not know which it got. Rotation is documented
and practised. No long-lived credential exists in CI — see the OIDC rule in the Python
[stack conventions](python/stack.md).

A secret in a repository is compromised from the moment it is committed, including in history.
Rotate it; removing the line is not a fix.

## 4. Personal data

Scan for personal data in CI, and sweep the full history on a schedule — the CI scan only sees
what changed. Design deletion at the same time as the tenancy model: which rows belong to whom
determines whether deletion is a query or a forensic exercise, and that is decided once.
