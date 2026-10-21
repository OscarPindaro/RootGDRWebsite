---
name: server-deploy
description: Prepare and verify an explicitly approved mini-server rollout through existing controller-side deployment tooling.
argument-hint: "<application and selected commit or artifact> [plan | check | apply]"
triggers: [user]
---

# Server deploy

Follow the [development workflow](../using-development-skills/SKILL.md) and
[mini-server procedures](../../shared/server-operations.md). Read the current
deployment manual and local command help. This skill does not authorize a
rollout merely by being installed or selected.

## Prepare the operation

Confirm one application and inventory target, selected full commit, version,
artifact path, intended configuration and expected downtime. Resolve whether the
request is planning, authorized check mode or an approved live operation.
Ambiguity means prepare and ask, not apply.

Review test evidence for the selected source. The existing proof requires the
recorded suites, timestamp and permitted proof mode; later production rollouts
need passing CI under the repository's policy. Do not forge an attestation or
substitute unrelated local test results.

Use `harness deploy build` and `check-artifact` when an approved build is needed.
The selected commit, not the dirty working tree, supplies build inputs. Record
the immutable image identity, architecture, version and archive checksum.
Local builds and downloads require their own applicable permission; checking
an artifact does not prove the source passed tests.

Review private input references without printing contents. Verify namespace,
listeners, persistent storage, separated database roles, capacity, current
deployment metadata, pinned helpers and recovery readiness. Do not initialize
credentials, accounts, storage repositories or firewall rules as a side effect.

Present the exact commands, target, files/resources affected, downtime,
verification and failure behavior. Obtain approval covering the intended
controller-side checks and writes. Use only existing deployment paths; new
applications and first bootstrap need their separately approved setup.

## Execute only the approved scope

Use the documented `harness deploy apply` path, or the separately documented
board operation only when that is the selected application. Check current help
and typed inputs; do not guess flags or use ad-hoc remote commands.
Do not remove `--check` or a global dry-run setting without approval for apply.
A successful check validates only the boundaries it actually exercised.

Preserve the shared operation lock, capacity checks, coordinated encrypted
pre-deploy backup and verified receipt before migration. Respect role separation
and the selected image identity after transfer. Never weaken a gate to finish.
Healthy unchanged reapplication may verify without restart; do not force one.

Stop on incompatible or unknown schema state, missing proof, failed backup,
insufficient space or ambiguous existing resources. Allow a previous-image/config
rollback only when included in the approved failure plan and the documented
Alembic compatibility checks pass. Otherwise retain the recovery marker and
report the blocker. Never restore production data or downgrade the schema.

## Verify and report

Verify readiness, deployed build/version/schema identity, real password login
and authorized authenticated reads. Do not use development login, reseed data
or create production records just to obtain a passing check.
Capture the project's required desktop/phone evidence when applicable.

Report selected commit, artifact, confirmed target, checks, deployment outcome
and remaining limits without credentials. Do not claim success from an active
service unit alone. Do not push Git, tag a release, change task-board records,
install a timer or broaden the deployment during this operation.
