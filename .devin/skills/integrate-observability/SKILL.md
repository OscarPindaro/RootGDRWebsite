---
name: integrate-observability
description: "Create, repair, or refactor team logging and telemetry export end to end in Python and TypeScript targets, including FastAPI, Next.js, workers, outbound calls, sensitive data, the provisioning handoff, and existing divergent integrations."
argument-hint: "<python|typescript>"
triggers: [user]
---

# Integrate observability

Follow the [development workflow](../using-development-skills/SKILL.md).
Retain the supplied Python and TypeScript contracts, shared-library integration
and export verification. Ask questions in plain prose. Resolve conflicts with
project instructions before editing, and preserve their approval, testing and
commit requirements. Obtain permission before network access or live telemetry
upload. Do not provision resources or credentials as part of this command.

Converge the target onto the observability contract, which is OpenTelemetry using the GenAI
semantic conventions where they apply. The vendor named in this skill is the export adapter that
contract currently selects, not the subject — instrument once, and the backend stays swappable.
The conventions own the facts; this owns the workflow.

Converge the target; there is no `check` mode. Use the current directory when no
path is given and accept one project path otherwise.

Use one target:

- `python` — FastAPI services on the shared library (`circlex-utils`), Gunicorn/Uvicorn, workers, subprocesses;
- `typescript` — Node services and Next.js apps on the shared observability wrapper (Next.js is one
  shape inside this target, not its own).

Read the target from the invocation or request. When it is absent, infer it
from the repository. When both stacks exist or the argument conflicts with the
files, present the evidence and confirm the target before editing.

## Load the target's contract

For `python`, read the [Python observability
contract](../../shared/conventions/python/observability.md), its
[executable patterns](../../shared/conventions/python/patterns/observability-patterns.md),
the [backend conventions](../../shared/conventions/python/backend.md), and the
[runtime patterns](../../shared/conventions/python/patterns/runtime-patterns.md)
when the target uses Gunicorn, multiple workers, or a container. Load
[LLM conventions](../../shared/conventions/python/llm.md) only when the target
uses an AI/LLM library. Use only the shared library's public primitives.

For `typescript`, read the [TypeScript observability
contract](../../shared/conventions/typescript/observability.md).

Consult a reference repository only when the contract cannot settle an
important target choice; do not copy its local structure blindly. Keep small
application adapters local and shaped for later extraction into the library.

## Discover

Confirm the project root, service entrypoints, process model, environment
settings, dependency style, and which of the contract's concerns the target
has: web framework, outbound clients, workers, subprocesses, queues, auth,
LLMs, bundler/standalone output.

Inventory every existing logging config and call path, every Logfire
configuration and instrumentation call, token/secret loading and local/test
opt-out, long-lived outbound clients and process boundaries, existing telemetry
tests, and real run commands.

Classify the base logging stack and each applicable concern as absent,
partial, divergent, or converged. Classify export into the states the loaded
contract defines.

Follow the full development loop. The approved plan must show the exact files,
what existing behavior is preserved, the deterministic proof, and whether live
upload can be verified.

## Converge

Establish the base logging stack first when it is missing. Migrate existing
pieces into one path; never layer a second bootstrap or logging config beside
the old one. Then apply the topology-relevant parts of the loaded contract:
library pinning, entrypoint configuration, export lifecycle, safe
instrumentation, sensitive-data policy, process/bundler boundaries, regression
tests, and the target's run/config documentation.

Preserve meaningful business spans and metrics; replace unsafe or duplicate
instrumentation without deleting target-specific telemetry. Never invent an
already-provisioned secret name — once an administrator supplies the secret
identifier, configure that exact value.

Do not create a Logfire project, write token, AWS secret, IAM policy, or cloud
resource. Those require an administrator.

## Prove and report

Run the target's focused tests, full quality gates, and real application
entrypoint. Prove spans and attributes deterministically without network
export, with the mechanism the loaded contract's Proof section names.

If no secret exists, finish successfully as **ready — provisioning pending**:
state that everything except upload is verified and provide the administrator
handoff from the loaded contract.

If a secret is declared, prove its startup behavior. Claim **live** only on the
records the loaded contract's Proof section requires. For a refactor of an
existing live integration, compare the attribute and resource-attribute keys
with a recent record. Otherwise state exactly which live evidence remains
unavailable.

When no gap exists, make no source change and report **already converged —
live** or **already converged — provisioning pending** from the available
evidence.

Finish the development loop with independent review and `align-docs`. Never
commit unless asked.
