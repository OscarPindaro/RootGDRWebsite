---
name: server-inspect
description: Diagnose a mini-server service from authorized read-only evidence without repairing or restarting it.
argument-hint: "[service] [symptom or overview] [time window]"
triggers: [user]
---

# Server inspect

Follow the [development workflow](../using-development-skills/SKILL.md) and
[mini-server procedures](../../shared/server-operations.md). This is report-only.
Read existing controller configuration and documentation first. Do not contact
the server without permission or bypass the project's direct-access restrictions.

## Scope and evidence

Identify the application, target, symptom and time window. Use the last six
hours when no period is stated, and label that default. Resolve an ambiguous
service before collecting private diagnostics.

Start with local deployment metadata, artifact manifests, recorded verification
and controller backup status. Use current command help to select read-only
operations. Dates on a receipt establish its age, not present server health.

With approved live evidence, examine only relevant service/container state,
readiness, deployed version, listener configuration, disk capacity and bounded
logs. Use sanitized, narrowly selected fields; avoid full configuration or
environment dumps. A running process or active systemd unit alone does not prove
application readiness.

Correlate errors with the deployed revision, schema, recent operations and
relevant source code. Distinguish the incident cause from secondary failures
and from an unverified hypothesis. Do not turn a historical warning into a
current outage.

## Report without repairs

Return the observed state, time and source of evidence, findings, likely cause,
checks still needed and proposed next action. Separate controller-only evidence
from live verification. If evidence is insufficient, say what is missing.

Do not restart services, run migrations, pull images, capture a backup, stop
writers, clear locks, change configuration or repair storage. Any correction
requires a separately approved operation. Save a redacted incident report only
when requested; do not modify the application or task board during inspection.
