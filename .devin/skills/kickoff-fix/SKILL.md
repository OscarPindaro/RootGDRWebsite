---
name: kickoff-fix
description: Route an explicitly requested existing-project assessment into the approved refactoring workflow without scaffolding over it.
argument-hint: "[existing project path or focus]"
triggers: [user]
---

# Kickoff fix

Follow the [development workflow](../using-development-skills/SKILL.md).
Resolve the existing project and requested focus without switching branches or
changing unrelated work.

Use the [read-only detector](../kickoff/scripts/detect-mode.sh). Continue for
`existing`; for a legacy `kickoff` marker, inspect unfinished work and confirm
whether to resume or audit it. Missing/empty targets belong to
[kickoff](../kickoff/SKILL.md); ambiguous contents need clarification.
Never scaffold over an existing project.

Use the [refactoring procedure](../refactor/SKILL.md) for a read-only audit,
evidence, priorities and bounded implementation batches. An explicit request for
an audit permits that audit without another ceremonial approval. It does not
authorize fixes, broad standards convergence, agents or environment changes.
Implementation follows existing ticket authority or an approved plan.

Preserve the target's architecture, runtime and harness unless a change is
explicitly approved. In this project, web UI remains JinjaX/htmx. Follow current
design guidance; the future UI-philosophy update is a separate request.
Do not apply generic company scaffolding, private libraries or Next.js defaults.

Follow the [project recipe](../kickoff/references/project-recipe.md) where
applicable. State missing prerequisites and preserve failing checks as failures.
Update affected documentation and make scoped local commits for approved,
completed changes. Audit-only findings remain in chat unless saving them was
requested. No push, release, deployment or external ticket creation is implied.
