---
name: server-delivery-audit
description: Audit mini-server build, CI, deployment and recovery configuration locally without executing a rollout.
argument-hint: "[repository or delivery scope]"
triggers: [user]
---

# Server delivery audit

Follow the [development workflow](../using-development-skills/SKILL.md) and
[mini-server procedures](../../shared/server-operations.md). Inspect locally
and report; do not deploy, build an image or contact the server.

Resolve the repository, intended application and delivery scope. Inspect
Dockerfiles, build inputs, CI, deployment commands/playbooks, configuration
schemas, manifests and relevant tests. Read called roles and effective commands,
not only the top-level workflow.

Check:

- Selected source commit, version and immutable image identity agree; transfer
  archives and manifests are validated before use.
- Production excludes source mounts, reload, development shortcuts and private
  controller files.
- CI verifies the intended source and does not deploy or obtain production
  credentials under this repository's policy.
- Dependency/image pins, effective build gates, context inputs and artifact
  comparisons are consistent; avoid duplicate work that adds no verification.
- Target inventory, rootless user, namespace, ports and persistent storage are
  explicit and do not overlap unrelated services.
- Bootstrap, migration and runtime credentials have distinct responsibilities.
- Readiness and authenticated verification establish deployed behavior rather
  than merely a running process.
- Backup receipt, lock handling, writer coordination, capacity checks and
  failure recovery are preserved.
- Rollback is schema-compatible; isolated restore cannot replace production.

Verify claims against code and configuration. Record missing runtime evidence
instead of asserting live safety from a local audit. Read relevant tests;
execute only authorized offline checks that cannot contact production or start
shared environments.

Report findings by impact with file/line evidence, affected behavior, effort,
dependencies and proposed verification. Distinguish policy differences from
defects. Group shared causes without inventing scores.
An audit request does not authorize fixing findings or changing CI, deployment,
credentials, network rules, release policy or external state.
