# Mini-server operations

Use the repository's controller-side tooling. These instructions adapt the
AWS inspection and delivery procedures to the existing mini-server deployment;
they do not install AWS tools or authorize a server operation.

## Sources and target

Read the [deployment manual](../../docs/features-implemented/production-deployment.md),
[approved server decisions](../../docs/features-request/REQ-0001-github-ci-and-manual-deployment.md)
and [CI guide](../../docs/ci.md), resolving dated or conflicting statements
against the current configuration and explicit owner decisions.

The documented target is a Fedora server with rootless Podman and user systemd
services. Existing private inventory, application manifests and operation inputs
supply the host, user, application base, namespace, image and ports. Do not treat
historical host addresses, versions or deployment outcomes as verified live state.
Confirm exactly one intended target and application before an operational command.

Use existing credential references without displaying values or searching for
alternative credentials. Do not print environment files, Vault contents,
passwords, signing keys, raw container environments or authentication headers.
Request sanitized fields and bounded, redacted logs.

## Permissions and separation

Installing or invoking a skill does not authorize live deployment, downtime,
backup execution, recovery or privileged setup. Name the exact target,
operation, expected writes, downtime, verification and failure response before
requesting approval. Ask before network access. Previous approval for another
operation, application or environment does not carry forward.

Follow the current prohibition on direct agent operations on production.
Use approved controller-side procedures; do not replace them with ad-hoc SSH
changes. When live diagnostics are not authorized or available, use local
artifacts and owner-provided evidence and state that live health is unknown.
Firewall, host privileges and owner-run setup remain separate.

Inspection and audit never repair. Ansible check mode is an operational
inspection requiring permission to contact its target; do not assume every
playbook task is harmless merely because `--check` is present.
Backups are writes and can stop application writers.

## Existing interfaces

Check local help before constructing commands:

- `harness deploy build` and `check-artifact` handle selected-commit image inputs.
- `harness deploy apply` invokes application rollout; `board` has its own scope.
- `harness deploy backup-status` reads controller backup status; `backup` performs
  coordinated weekly capture and configured managed-snapshot retention. Disclose
  that deletion scope and obtain specific approval before using that entry point.
  Timer installation is a separate persistent change.
- `deploy/backup.yaml` and `deploy/restore.yaml` use typed private specifications.
  Restore is controller-side and only targets a new isolated namespace.

These names were checked locally; invocation details come from current help,
the manual and approved private inputs. Do not invent missing status, rollback,
repair or production-restore subcommands.

## Recovery and data boundaries

Respect the shared operation lock and pending-recovery markers. Never steal a
lock or clear markers to force progress. Preserve unrelated applications, bot
services, local board demonstrations, test, scratch and showcase data.

Deployment requires a verified coordinated encrypted pre-deploy backup before
migrations. Preserve separate bootstrap, migrator and runtime database roles.
App rollback requires verified schema compatibility; never automatically restore
production data or downgrade Alembic.

Use only declared resources and run-owned temporary staging. Existing-volume
inspection must preserve ownership; follow the documented canonical mountpoint
procedure rather than mounting named volumes with an arbitrary helper user.
Never prune globally, delete unrelated resources, rotate credentials, reseed
existing data or activate a recovered stack as a shortcut.
