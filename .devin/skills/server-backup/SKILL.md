---
name: server-backup
description: Check backup status or perform an explicitly approved coordinated capture or isolated recovery using existing controller procedures.
argument-hint: "[status | capture | restore-check] [application and approved inputs]"
triggers: [user]
---

# Server backup

Follow the [development workflow](../using-development-skills/SKILL.md) and
[mini-server procedures](../../shared/server-operations.md).
Distinguish status, capture and isolated recovery. If no operation is clear,
start with local status or ask; do not assume permission to stop writers.
No mode permits production restoration.

## Status

Read the approved controller backup configuration references and use the
documented `harness deploy backup-status` interface. It reports last success,
failure and overdue state without credentials. Do not contact the server,
run a capture, install a timer or initialize a restic repository to answer status.

Distinguish a dated success record from current integrity or recoverability.
Missing configuration or unavailable receipts are evidence gaps, not permission
to find credentials elsewhere. Propose a verification operation separately.

## Coordinated capture

Confirm application, target, purpose, writer identities, storage sources,
destination, required configuration and downtime. Use existing typed private
inputs and the documented backup playbook/controller interface.
Obtain approval for writer stops, capture, transfer, encryption and verification.

The weekly `harness deploy backup` operation also applies configured retention.
Before using it, disclose the policy and specifically affected managed snapshot
IDs and obtain deletion approval. If that scope cannot be established, do not
invoke the weekly operation: propose the documented capture-only procedure
instead. Do not alter retention settings or invent a bypass flag.

Respect the shared lock. Capture only after declared writers stop and identities
are checked; refuse paused or unexpectedly restarted writers. Use the documented
PostgreSQL dump or SQLite backup mechanism together with uploads/attachments and
required recovery configuration, not a live database-directory copy.

Verify transfer checksums, encrypted repository read-back and isolated receipt
validation before claiming a backup succeeded. Keep plaintext staging private.
For pre-deploy capture, back up current configuration before publishing candidate
files. Preserve the documented resume policy: weekly capture resumes previously
running writers; a verified pre-deploy capture leaves control to the rollout.
On failure, resume only the unchanged writers allowed by the existing procedure.

Never steal locks, prune globally, delete unmanaged or pre-deploy snapshots,
rotate credentials or remove unowned staging. Schedule/timer changes require
their own approval.

## Isolated recovery verification

Obtain approval for the exact snapshot/receipt, new target namespace, storage,
resource use and verification. Use `deploy/restore.yaml` and the typed restore
specification. Require the documented `rootgdr-restore-...` namespace, an existing
parent and a new canonical target directory. Existing targets, even empty ones,
are refused; do not delete them to make the request pass.

Keep the restored database disconnected by default. A published port must be
explicitly approved and loopback-only. Verify manifest, schema, row counts,
roles/grants, files, ownership and relevant application behavior inside the
recovered target. Do not activate it over production, change routing or replace
live configuration.

Retain the isolated target for inspection according to the existing procedure.
Approve any cleanup separately and remove only resources positively owned by
that operation after their environments are stopped.

Report snapshot/receipt identity, application, verification, writer state,
remaining resources and failures without secrets. Do not equate a command exit
code, successful dump or snapshot listing with verified recoverability.
