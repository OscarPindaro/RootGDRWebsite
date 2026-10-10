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

## Manual Ansible rollout

`deploy/deploy.yaml` requires exactly one explicitly inventoried target and keeps
orchestration in `rootgdr_application` and `image_transfer`. The controller CLI
invokes that playbook with argv, existing SSH authentication and private inputs:

```console
uv run harness deploy apply --inventory /private/inventory.yaml \
  --vars-file /private/deployment.vault.yaml \
  --vault-password-file /private/vault-password \
  --manifest /private/build/image.json --check
```

Remove `--check` only for the manually approved rollout. Global `--dry-run` also
uses check mode: validate the typed configuration/proof/archive without builds,
helper installation, writer stops or target filesystem mutation. Templates in
`deploy/inventory.example.yaml` and `deploy/vars.example.yaml` contain no usable
credentials; keep real vars, the five separated configuration files, repository
password and Vault password outside Git, mode 0600. Mounted YAML/init files live
inside a private 0700 release directory and are readable by their container users;
env files remain 0600. Secret tasks suppress output and diffs. The facade never
prints captured Ansible output, including malformed private variable diagnostics.

A proof records the selected full commit, four passing suites, aware timestamp
and `local-bootstrap` or `ci` mode. It is an operator attestation, not an automatic
query of hosted CI. Only the first production bootstrap accepts local mode;
later mutating production rollout requires recorded passing CI. Healthy unchanged
image/configuration/secret generation is verified with real login and read-only
checks without restart, backup or migration. The private current manifest is
published atomically only after successful readiness, build and authenticated reads.

Preflight validates namespace/listener/configuration, pinned tools/images and
space for transfer, unpacking, coordinated capture and a 512 MiB operating reserve.
Existing containers/volumes without a current manifest require operator review;
ordinary rollout refuses database credential rotation. Images move as checksummed
archives over Ansible's connection and are checked by immutable ID after load.
Server helper/provider environments are user-scoped, pinned and separate from the
runtime; only declared temporary staging is removed. No global image/volume prune.
PostgreSQL initialization reads passwords with psql `\getenv`, never password argv.

The shared operation lock covers pre-deploy encrypted backup and one-shot DDL
migration. Runtime then uses DML credentials. On failure, one previous-image/config
rollback is allowed only when the before/after Alembic heads match its verified
manifest. Different/unknown schema or failed rollback stops writers and leaves
`.pending-recovery` for operator review. No deploy rescue calls restore or downgrade.
A namespaced native user service retains the selected configuration across restart;
startup still needs `/health/ready`, not merely an active systemd unit.

Read-only helpers bind an existing volume's canonical mountpoint instead of
mounting it by name: Podman otherwise chowns the volume root to the helper user,
even on a read-only mount. Capture/capacity checks preserve runtime UID/GID/modes.

## Owner-run LAN firewall setup

`deploy/server-setup.yaml` is separate from application rollout. Run it from the
repository on the PC; `--ask-become-pass` prompts locally for the server's sudo
password. It requires exactly one host in the existing `rootgdr_targets` inventory.

```console
ANSIBLE_CONFIG=deploy/ansible.cfg ansible-playbook \
  -i ~/.config/devin/rootgdr/inventory.yaml deploy/server-setup.yaml \
  --ask-become-pass --check

ANSIBLE_CONFIG=deploy/ansible.cfg ansible-playbook \
  -i ~/.config/devin/rootgdr/inventory.yaml deploy/server-setup.yaml \
  --ask-become-pass
```

The approved rule allows only IPv4 `192.168.1.0/24` to TCP 8001 in `FedoraServer`.
The zone check accepts firewalld's optional `(default)` annotation. The playbook
refuses an inactive zone or failed firewall query, then adds only missing
runtime/permanent copies. It does not reload the firewall, change other
rules, install packages, start services or touch application data. Check mode
runs read-only queries and reports missing rules without applying them; reapply
with both copies present reports no changes. Ordinary deploys remain unprivileged.

Ansible syntax and local execution checks cover check mode, partial rule state,
repeat application, query failures and inventory/zone rejection using an isolated
firewall-command stand-in. The owner applies the real privileged rule; then verify
`http://192.168.1.201:8001/health/ready` from the PC and login from a LAN phone.

## Separate planning-board deployment

`deploy/vikunja.yaml` and the `vikunja` role bootstrap or verify one explicitly
inventoried `vikunja_targets` host. The local demonstration Compose and Kanboard
are not inputs. Vikunja 2.6.0 and the Python storage helper are digest-pinned;
controller-cached images are exported as private OCI archives and transferred
through the existing checksummed `image_transfer` role, without server pulls.

```console
uv run harness deploy board --inventory /private/board-inventory.yaml \
  --vars-file /private/board.vault.yaml \
  --vault-password-file /private/vault-password --check
```

Removing `--check` explicitly invokes bootstrap. `deploy/vikunja.vars.example.yaml`
shows the typed private inputs: unique run/secret UUIDs, full deployment commit,
canonical board base, loopback port, signing-secret file, owner credentials and
owned `bot-` tooling account. A live bootstrap requires a matching passing proof
for unit/frontend/integration/E2E. Generate dedicated credentials privately;
store the controller inputs in Vault, never command arguments. The server runs
only minimal pinned Python/HTTP and Compose environments under its board base.

The owner logs in normally. The tooling bot has no password or email, receives
read/write access only to the real project, and uses an API v2 token with reviewed
project/view/bucket/task/comment scopes. It cannot manage tokens or create/delete
projects. The token expires after one year; expiration is a reported verification
failure, not an automatic token/account reset. Registration is temporarily enabled
only on loopback for a new bootstrap and is closed on success or failure. Mail,
reminders and public link sharing remain disabled. The private runtime directory
contains owner credentials and the tooling token; read-only container signing-secret
mounts are protected by the 0700 application/runtime directories on the host.

The shared atomic operation lock covers initialization and verification. Existing
storage without `current.json`, a stale lock or `.pending-bootstrap` is refused
for operator review. Unchanged reapply verifies the owner, bot, token and listener
without recreating accounts or restarting the writer; systemd user restart preserves
SQLite and attachments. Configuration/image/credential changes are deliberately
refused: upgrades require a separately reviewed coordinated recovery-gated rollout.
Runtime binds use canonical mountpoints of the dedicated database/attachment
volumes, avoiding Podman's repeated volume-root ownership changes.

To capture the verified board, invoke its private helper's `capture-spec --plan
<board-base>/runtime/deployment-plan.json` and supply that typed result to
`deploy/backup.yaml`. The helper assigns a fresh capture UUID; `--purpose predeploy`
selects the migration gate rather than the default weekly resume policy.
The specification includes SQLite, attachments, closed configuration, Compose/env,
signing secret, owner credentials, tooling token and deployment identity. The
existing coordinated role stops writers, transfers/encrypts the snapshot on the
PC, verifies read-back and resumes the unchanged writer for weekly capture.
`deploy/restore.yaml` restores only a new `rootgdr-restore-...` target. Real local
checks recover password login, task data, attachment bytes and the restricted token;
they do not activate recovered data over the source stack. Keep recovery credentials
and an offline repository copy securely. No timer or production restore is activated.

For PC access, use an explicitly chosen tunnel distinct from the local demo, for
example `ssh -N -L 3458:127.0.0.1:3458 pinball@pinball-server.local` for the ports in
the example variables. The `access_port` is the PC-side frontend URL; `target.port`
is the server-side loopback listener. Server activation remains a separate step.

## First-bootstrap reference seed

The first rollout of a new production stack also seeds the committed reference
world (`seed/boschetto-di-smeraldo.yaml`). `rollout_cli seed-request` converts the
YAML on the controller — PyYAML never enters the pinned runtime — and the role
mounts that private request into a one-shot container of the **selected immutable
image**. `backend.content.bootstrap` refuses to run outside `env: production` or
when `ROOTGDR_BUILD_COMMIT` differs from the selected commit, then, inside one
transaction, takes an advisory lock on the owner email and either imports the
bundle or returns `preserved`. Any existing world of that owner is never reset,
renamed or duplicated; later rollouts skip the seed entirely. The typed outcome
(`created`/`preserved` plus the world id) is asserted and the authenticated reads
run again, so the verification proves the seeded reference world through the real
password login.

## First live bootstrap

Both new isolated stacks were bootstrapped manually on `pinball-server.local`
(Fedora 43 Server, x86-64, rootless Podman 5.8.4) from the verified commit
`c7d61d9dff6b578e50bfcfebb30f30a409a3c9aa`, application version `0.1.0`.

- Root GDR: `/home/pinball/rootgdr-production`, published on
  `192.168.1.201:8001`, Alembic head `c35a50fec1ae`, image
  `sha256:af0a9741b586…`, native user service `rootgdr-production.service`
  enabled and active, `current.json` published after verification.
- Board: `/home/pinball/rootgdr-vikunja`, loopback-only `127.0.0.1:3458`, image
  `0838aba019fa…`, owner `oscar` (id 1), owned tooling bot
  `bot-rootgdr-tooling` (id 2), project `Root GDR` (id 2), scoped token (id 1),
  `rootgdr-vikunja.service` enabled and active.

The pre-deploy coordinated backup was encrypted into the PC repository under
`~/.local/share/rootgdr/backups/repository` with its receipt in
`predeploy/`. Verification used real password logins, `/health/ready`,
`/version`, the seeded reference world and an authenticated Vikunja read; the
desktop, Pixel-7-class and 390×844 captures were reviewed. Both stacks were
reached through explicit SSH tunnels for verification because the server
firewall does not yet admit port 8001 from the LAN — that opening is Oscar's
action, and LAN access from a phone remains the open gate.

The failed first attempt is worth remembering: the reviewed helper image had
been transferred as an archive, so it existed only by immutable ID on the
target and the pinned digest reference did not resolve there. The first
coordinated capture failed after downtime and the rollout stopped without
touching data; the plan, durable manifest and capture/capacity/board paths now
carry the immutable helper identity. Cleanup removed only that attempt's
containers, volumes and release directory, after confirming zero user tables
and no Alembic version.

## Weekly backup operation

`deploy/weekly-backup.yaml` runs only capture, encryption and verification; it
never deploys, migrates or restores. For every configured application it asks the
target's own pinned helper for a typed `--purpose weekly` capture specification,
then runs the coordinated role under that application's shared lock. A periodic
specification always gets a fresh run UUID, so its receipt cannot collide with the
deployment's pre-deploy receipt.

```console
uv run harness deploy install-backup-timer --config /private/weekly.json --enable
uv run harness deploy backup --config /private/weekly.json
uv run harness deploy backup-status --config /private/weekly.json
```

`WeeklyBackupConfig` is a private controller file with paths only: inventory,
Vault file and password file, the restic `StorageSpec`, receipt and status
directories, and per-application `base`, CLI module and relative plan path.
Secrets stay in Vault, and the timer reaches them non-interactively through the
private Vault password file — no prompt, no interactive unlock.

`deploy/systemd/rootgdr-weekly-backup.{service,timer}` are the committed
templates. The timer is `OnCalendar=Sun *-*-* 10:00:00 Europe/Rome` with
`Persistent=true`, so a missed Sunday runs after the next boot. The installed
service invokes only `harness deploy backup`.

Retention keeps the newest four complete weekly snapshots **per application**.
It reads restic's snapshot list, accepts only records tagged
`rootgdr-managed-v1` **and** `purpose=weekly` with exactly one application and run
tag, and forgets only the superseded ones. Pre-deploy snapshots, other
applications and unmanaged restic data are never selected. Pruning runs only
after a new verified snapshot exists, so a failed or partial capture can never
remove the last valid copy; there is no path-based deletion and no symlink
handling to get wrong.

`harness deploy backup-status` prints last success, last failure, the bounded last
error and whether the copy is overdue (no verified weekly success within eight
days, i.e. one interval plus a declared one-day margin). The service's journal
holds the rest. A PC that stays off, an unreachable server or an unavailable
Vault password delay the copy and surface as overdue; a seven-day recovery point
is therefore not promised while the PC is offline.

Verified on the real stacks: two consecutive weekly runs produced distinct
encrypted snapshots for both applications, a deliberate second run before the
run-ID fix failed at the encryption gate, resumed the unchanged writer, preserved
every earlier snapshot and recorded the failure, and a disposable
`rootgdr-restore-…` target restored the newest Root GDR weekly snapshot with its
schema, grants and configuration.

## Backlog CLI

`harness backlog` reads, creates and moves tickets on the isolated board over
API v2. It never deletes anything and never administers projects, tokens or
users.

```console
export ROOTGDR_BOARD_TOKEN_FILE=/private/board-tooling-token
uv run harness backlog projects [--json]
uv run harness backlog list --project 2 [--query REQ-] [--json]
uv run harness backlog show 17 [--json]
uv run harness backlog create --project 2 --title "REQ-0012/T04 …" --description "…"
uv run harness backlog workflow --project 2 [--view 12] [--json]
uv run harness backlog import --project 2 --view 12 --bucket 13 [--dry-run] [--json]
uv run harness backlog move 17 --project 2 --view 3 --bucket 8 [--json]
uv run harness backlog close 17 --project 2 --view 3 [--json]
uv run harness backlog reopen 17 --project 2 --view 3 [--bucket 7] [--json]
uv run harness backlog comment 17 --text "…" --marker REQ-0012/T04 [--json]
uv run harness backlog attach 17 /path/to/image.png /path/to/image.jpg [--json]
uv run harness backlog attachments 17 [--json]
uv run harness backlog check-requests
```

`workflow` is the owner-side setup command: it configures the project's kanban
view — reusing and renaming the buckets a new view starts with — so `Backlog`,
`In corso`, `Review` and `Conclusi` exist with explicit default and done bucket
ids, and it prints those ids for the other commands. It needs a token allowed to
create views and buckets, so the owner's, not the tooling token; a re-run is a
no-op.

`import` reads the cycle plan's ticket headings — the approved list plus the
deferred `REQ-0001/T01` — and creates only the tickets missing from the board.
The stable `REQ-nnnn/Tnn` key is the title prefix, the description links the
request document and the plan section, and each new card is placed in the given
bucket. Existing cards are never touched, so manual progress, descriptions and
placement survive a re-import; a duplicate key already on the board is an
error, not fuzzy matching; `--dry-run` writes nothing. Follow-up tickets that
the plan's ticket sections do not define (for example the later REQ-0001/T10
and T11 or REQ-0011/T09–T10) are created with `create` and closed with the
same commands, using the request document as their specification.

`move`, `close` and `reopen` read the current placement first, so a repeat or a
retry after an ambiguous timeout is a reported no-op instead of a second write.
`close` places the task in the view's `done_bucket_id` (which is what marks it
done in Vikunja); without a done bucket only the `done` flag is patched.
`reopen` places it back in the view's default bucket, or an explicit one, and
never into the done bucket. `comment --marker` is idempotent: the marker is
appended to the posted body, an existing marker is left alone, and a timeout
re-reads before concluding anything. The `done` flag is patched with a minimal
JSON merge patch that never rewrites title, description or rich text.

`attach` streams explicitly named files as multipart attachments, including
PNG/JPEG images. Before uploading it checks existing filename/size candidates
and downloads them to compare SHA-256; an identical file is reused. New uploads
are listed and downloaded again to verify their stored bytes. Per-file failures
inside a 201 response are failures, not successful uploads. An ambiguous timeout,
server error or invalid upload response triggers read-back, never a blind POST
retry. This is sequential retry protection, not atomic deduplication across
concurrent clients. Read-back currently buffers one attachment in memory.

Batches upload sequentially and stop on failure. Earlier verified attachments
remain; JSON reports `complete: false` with their IDs, metadata and hashes, and
the command exits nonzero. No attachment is deleted or replaced. Validate every
input path before starting a batch. `attachments` lists paginated metadata for
inspection, without downloading file bodies. Store image evidence on Vikunja
when requested; the repository specification can retain captions and confirmed
attachment IDs instead of committed image files.

These operations require `tasks_attachments.read_all`, `read_one` and `create`
scopes, verified against the pinned board's route registry. No delete scope is
needed. Existing bootstrap/live tokens are unchanged: the owner must deliberately
provide an appropriately scoped private token. The CLI never creates, rotates
or expands credentials. It also rejects redirects and URL userinfo rather than
forwarding a bearer token away from the explicit loopback tunnel.

`BoardClient` is a typed httpx boundary: project, view, bucket, task, comment,
attachment, upload response and receipt models; `BoardPage` for the v2 envelope;
and full pagination up to a reviewed bound. Status codes map to bounded messages:
401/403 "missing, expired or insufficiently scoped", 404 "not found", and
422 "rejected the request payload" —
and never echo an upstream body. Transport failure and timeout are distinguished
from a server rejection, so an ambiguous write is never retried blindly.

Credentials come from `--token-file` or `ROOTGDR_BOARD_TOKEN_FILE`, must be a
canonical `0600` file, and never appear in argv, output or logs. The base URL
must be an explicit loopback tunnel, matching the deployed board. Human output
prints ids and titles only; `--json` prints the full records. Placement reads
need the reviewed `projects.views_buckets_tasks_get` token scope, which the
bootstrap now requests; a token created before that scope existed must be
recreated deliberately before `move`, `close` or `reopen` can read placements.

Verified against the real isolated 2.6.0 board and against the live server board
through its tunnel: pagination across more than one page (55 tasks), create with
read-back, 404, 422, a wrong token and the tooling scope that resolves only the
real project. Later verification added a real kanban workflow: move with a
repeated no-op, close into the done bucket, reopen into the default bucket, one
comment for a repeated marker, a read-only token refused on write, and a
description preserved across a `done` patch.

## Limits

Packaging, readiness, coordinated backup, isolated recovery and manual rollout
are implemented locally; this is not evidence of a completed server deployment.
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
