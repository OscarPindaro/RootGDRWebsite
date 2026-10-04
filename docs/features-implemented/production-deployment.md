# Manual production deployment

A locally built Root GDR image and a separate Compose definition for persistent
runtime data, without source mounts or development reload.

## What it does

- The image installs frozen production dependencies, runs as UID/GID 10001 and
  contains application/assets, migrations and the MIT notice. Its build context
  excludes local configuration, credentials, uploads, browsers, Node packages,
  tests and harness artifacts.
- `deploy/production.compose.yaml` consumes an explicitly selected image instead
  of building or pulling application images. PostgreSQL and uploads use separate
  persistent volumes in the explicitly named Compose project.
- Database bootstrap, one-shot migration and application runtime have distinct
  environment files. The runtime can start without migration credentials;
  Alembic refuses to proceed when its own credentials are missing.
- The application and maintenance container use a read-only root filesystem,
  bounded writable temporary storage and no elevated capabilities. Uploads stay
  writable outside the image. The database is not published on the host.
- `/health/ready` checks the real database, its Alembic revision and a temporary
  storage write/read, returning 503 when a dependency is not ready. `/ping`
  remains liveness; `/version` reports application version, build and schema
  heads without requiring deployment credentials.
- Production does not register development login, showcase or content-import
  shortcuts. The deployment verifier uses real password login and authenticated
  API/HTML reads, including an available world image, and can require the selected
  commit. It never substitutes development authentication.

## How it is built

The root Dockerfile copies only allowlisted sources and installs with
`uv sync --frozen --no-dev`. The virtual environment lives under `/opt/venv`;
build-time uv caches are cleaned so Podman's temporary-directory copy-up fits
the 64 MB runtime tmpfs. Browser tests run on the host, not inside this image.

`BUILD_COMMIT` is consumed by a build step before the OCI revision label and
runtime environment are set: Podman's cached metadata-only instructions must
not inherit another build's argument value. Cached-build integration checks
verify both the label and runtime revision for distinct selected values.
The caller must select and record a clean commit and the resulting image ID;
`verification` builds are only disposable test images. The migration service is
in the maintenance profile and is invoked explicitly before application rollout.

Database and image integration checks verify runtime DML-only grants, startup
without migration secrets, private-file exclusion and upload persistence across
container recreation. SQL statement parameter echo is disabled by default.

## Selected-commit image artifacts

`uv run harness deploy build --revision <commit> --output-dir <new-directory>`
archives the selected Git commit into private temporary staging, builds that
source, checks Linux/amd64, the OCI revision, runtime build environment and installed
package version, then saves the image next to a typed `image.json` manifest.
Local uncommitted edits and untracked files are not build inputs. Existing output
directories are refused; a failed build removes only its own new artifact directory.

The manifest records the full commit, immutable image ID, version, architecture,
archive size and SHA-256. `harness deploy check-artifact <absolute-image.json>`
validates it and reads the archive back. With Podman the archive is OCI; Docker's
native save format is used for Docker. Files are private and never published to a
registry. `harness --dry-run deploy build ...` creates nothing and builds nothing.
These checks establish artifact identity, not a passing CI/test receipt or a
completed deployment. The transfer/rollout playbook must still check its target,
loaded image ID, verified tests, available space, configuration and recovery gate.

## Coordinated encrypted backups

`deploy/backup.yaml` invokes `coordinated_backup` for explicit `backup_targets`.
The application base must already exist. The role takes an atomic shared
`.operation-lock`, records the run UUID, records original writer states, then
stops every declared writer and waits for shutdown. A stale lock is an operator
error; the role never steals one. Deploy roles holding the same lock call this
role with `backup_manage_lock: false` and the matching run UUID, keeping their
lock across backup and migrations.

The private JSON `CaptureSpec` is validated by
`python -m harness.deploy.backup_cli capture`. It contains application
(`rootgdr`/`vikunja`), purpose (`weekly`/`predeploy`), UUID, full deployment Git
commit, immutable image ID, explicit writer container names, database and file
sources, and named recovery configuration files. Pre-deploy specifications describe
the **current** build/configuration, not the candidate: stage new configuration
elsewhere until the old files and credentials have been backed up. Capture independently refuses
running **or paused** writers and rechecks container identities/lifecycle after
capture, detecting a restart during the snapshot. The role refuses already-paused
writers without unpausing them. The declared writer list is an operator boundary:
add any future worker before enabling it; unrelated external DB writers are not
magically discovered or stopped.

- Root GDR: PostgreSQL custom-format logical dump, never a live PGDATA copy.
  The two login roles are recreated from their password verifiers; database,
  schema, object ownership, explicit/default grants and Alembic heads are checked.
  An initialized empty database is backed up with no Alembic heads before the
  first migration; a nonempty database lacking Alembic identity is refused. For
  first bootstrap, provision the app container in a stopped state before backup
  (do not start the application just to establish its writer identity).
  Custom privileged roles, role memberships or nonstandard role settings need a
  reviewed extension instead of silent omission.
- Vikunja: separate SQLite backup-API snapshot, with integrity/schema/table checks,
  plus separate attachments. Neither source references a local board demo.
- Files: read-only directory or an **existing** named volume. Archives reject
  links, traversal, duplicates and special nodes; checksums and numeric UID/GID,
  modes and sizes are recorded and verified after isolated restoration.
- Required configuration names for Root are `runtime_env`, `runtime_config`,
  `migration_env`, `migration_config`, `database_env`, `compose_env`, `compose`.
  Vikunja requires `configuration`, `secrets`, `compose`. Supply the actual files,
  including dedicated credentials/signing secrets and all additional material
  needed to reconstruct the service; names alone do not validate their contents.

Manifests are typed/versioned, carry build/schema identifiers, and checksum every
artifact. Plaintext staging is private (directories 0700, completed files 0600),
transferred over Ansible's trusted connection, and removed in `always` only when
created by this invocation. Transfer checksums and controller bundle validation
must both pass.

Encryption uses maintained **restic 0.19.1**, pinned to image digest, instead of
the plan's candidate age installer. This preserves complete weekly/pre-deploy
recovery snapshots without introducing custom cryptography. The dedicated random
repository password exists **only on the PC**, in a private file; keep another
secure offline copy. The server receives no repository password. Helper Python
and PostgreSQL 18.3 restore are also digest-pinned; all container runs use
`--pull=never`, so provision these reviewed images before downtime.

Initialize an empty private controller repository explicitly, never during deploy:

```console
python -m harness.deploy.backup_cli init-storage --storage /private/storage.json
```

`StorageSpec` JSON specifies absolute `repository`, `password_file` and optional
engine (`podman` default, or `docker`). Use the approved destination
`~/.local/share/rootgdr/backups/repository`, expanded to an absolute path, mode
0700; store the password and specification outside Git (password mode 0600).
The approved weekly schedule is Sunday 10:00 **Europe/Rome**, keeping four complete
weekly snapshots **per application** after a verified replacement. Pre-deploy
snapshots are separately tagged and have no automatic expiry. This ticket does
not install a timer or prune snapshots; activation, retention and age/failure
status belong to REQ-0001/T08.

`seal` checks the transferred bundle, writes an encrypted tagged restic snapshot,
reads repository data back with `check --read-data`, restores that snapshot to
private temporary staging, and verifies its manifest/checksums again. Only then
is a private `BackupReceipt` published and `backup_verified` set to true. Receipts
contain the exact snapshot/manifest IDs and run UUID. Failure blocks migrations,
removes run-owned staging and resumes only previously running containers of the
**unchanged build**. Successful weekly backup resumes them; successful pre-deploy
backup leaves them stopped for the caller's migration. No backup path migrates or
restores application data.

Role inputs are `backup_spec`, `backup_application_base`, argv lists
`backup_capture_command`/`backup_controller_command`, and controller-only paths
`backup_storage_file`/`backup_receipt_file`. Both commands invoke the same pinned
module/Pydantic environment. The server therefore needs a separately provisioned
Python environment containing this backup package and its locked Pydantic
runtime; the full development harness is not installed by this backup role.
Check mode validates supplied boundaries without capture, encryption, writer
stops or filesystem mutation. Keep private vars in Vault; secret-bearing task
output/diffs are suppressed.

## Isolated recovery

`deploy/restore.yaml` is controller-only and is never a deploy rescue. Supply
`restore_command` (argv prefix ending in `-m harness.deploy.backup_cli`),
`restore_storage_file`, `restore_receipt_file`, `restore_spec_file`:

```console
ansible-playbook deploy/restore.yaml -e @/private/recovery-vars.yaml
```

`RestoreSpec` must name `rootgdr-restore-<unique suffix>` (8–41 lowercase
letters/digits/hyphens), with an absolute canonical target directory whose final
component is exactly that namespace. Live/default namespaces, symlinks, existing
containers and **all existing target directories, even empty ones**, are refused.
The parent must already exist. Recovery decrypts the exact receipt's snapshot,
checks it, then creates only new storage and (for PostgreSQL) a new isolated
container with a fresh random administrator password. It does not reuse source
admin secrets or grant runtime DDL. The supported source administrator is
`postgres`; two application login roles are restored with their original
verifiers. DB/schema/row counts/grants and files/ownership are checked before
writing `recovery.json`. SQLite is copied again through its backup API.

By default the recovery DB has no network and no published port. Explicit
`publish_database: true` permits an engine-allocated **loopback-only** port for
real application verification with the recovered config and uploads. Successful
recovery leaves its disposable container/storage for inspection. Failure stops
only a container positively created by that run and retains the isolated target
for diagnosis. The operator removes only that namespace after review.

## Limits

Packaging, readiness, coordinated backup and isolated recovery are implemented;
this is not evidence of a completed server deployment. Application rollout and
schema-compatible rollback remain
[REQ-0001](../features-request/REQ-0001-github-ci-and-manual-deployment.md)/T06.
No automatic destructive production restore, Alembic downgrade, WAL/PITR, timer,
retention cleanup or production activation is supplied here. A same-disk copy
cannot cover server loss; the verified repository must remain on the PC.
Recovery tests currently exercise rootless Podman. Clean runners must provision
Podman/Compose, select `HARNESS_CONTAINER_ENGINE=podman`, and preload the pinned
helper, PostgreSQL and restic images before running recovery tests. Docker
transport selection has not been independently verified. SSH transfer and live
server activation require the deployment coordinator's separate disposable/live
checks; tests here use a disposable local Ansible connection.
Snapshots are logically complete but physically deduplicated/encrypted, not
standalone age archives. Keep the repository and its password together in a
secure recovery plan. Original configuration/credentials are recovered, not
blindly activated against a live service. Version selection remains manual;
the revision label is not a release number.
