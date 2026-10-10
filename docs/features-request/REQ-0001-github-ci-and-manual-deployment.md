---
id: REQ-0001
requested_on: 2026-10-03
title: GitHub CI and manual home-server deployment
---

# GitHub CI and manual home-server deployment

Record the decisions from the 2026-10-03 discussion. Creating this request does
not authorize implementation, GitHub settings changes, pushes, deployment, or
restoration of production data. Vikunja is the selected authority for backlog
and ticket status; this document owns the specification. Its demo cards are not
real implementation tickets.

## Approved cycle decisions — 2026-10-03

The approved infrastructure and document cycle supersedes the initial identity
proposal below. Implementation proceeds ticket by ticket, with tests and visual
evidence. Current ticket status belongs in Vikunja, not this document.

- Defer REQ-0001/T01: no GitHub App, mandatory PR workflow or branch-policy
  changes in this cycle. Use the existing Git authentication without modifying
  global configuration; normally push verified commits to `main` at cycle end.
  Do not use authenticated `gh` reads of settings or billing.
- The repository is public. CI runs on PRs targeting `main`, pushes to `main`
  and manual dispatch; it never deploys. Keep failed checks failed.
- Build and invoke Ansible locally, then transfer images over the existing SSH
  connection to `pinball@pinball-server.local`. The server is Fedora 43 Server,
  x86-64, with rootless Podman and user lingering already enabled. Install a
  pinned Compose provider in a dedicated user environment, without sudo.
- Deploy new, isolated Root GDR and Vikunja stacks. Preserve the server's old
  checkout, bot services, local board trials, scratch and showcase data.
- Root GDR uses HTTP on the trusted IPv4 LAN at `192.168.1.201:8001`, a production
  configuration and real password login. `cookie_secure: false` is limited to
  that explicitly chosen LAN profile. Oscar opens the firewall for the LAN.
  Vikunja is loopback-only on the server and reached from the PC by SSH tunnel.
- Bootstrap Oscar with `oscar.pindaro@gmail.com`, dedicated privately generated
  credentials, and only the committed reference world. Do not reset existing
  accounts or reseed over user edits on later deployments.
- The first bootstrap may precede publication of CI after local checks and
  disposable deployment/recovery tests pass. This does not permit ignoring a
  failing test or a subsequently observed failed CI run.
- Take a coordinated, encrypted pre-deploy backup. Also back up weekly to this
  PC at `~/.local/share/rootgdr/backups`, Sunday 10:00 Europe/Rome. Keep four
  complete weekly copies per application; retain pre-deploy copies separately.
  Delete only managed older weekly copies after a verified replacement.
- Stop writers for capture and verify restoration in an isolated target. Never
  automatically restore production data or downgrade Alembic. App rollback
  requires proven schema compatibility; insufficient disk space is a blocker,
  not permission to prune unrelated images or volumes.
- Additional cycle tickets cover current identity references (T00), first live
  bootstrap (T07), weekly backup operation (T08), and final audit/push/rollout
  (T09). A local cached-build regression found during verification adds T10:
  consume the selected build argument before metadata-only instructions and
  verify distinct cached revisions in both OCI labels and runtime information.
  T11 splits selected-commit artifact creation/validation from the larger T06
  orchestration ticket: private archives, typed manifest, immutable image ID,
  revision/version/architecture and transfer checksum checks. T06 depends on T11.
  T03/T04/T05/T06 retain their packaging, recovery, readiness and Ansible
  boundaries. Version selection, tags and release publication remain separate.

The implementation plan also covers REQ-0002–REQ-0010, the harness follow-up,
and planning/release tooling. Independent tickets may use at most three
isolated worktrees after the server bootstrap, with coordinator review and
verification. Agents never operate directly on the production server.

## Approved firewall follow-up — 2026-10-10

Oscar requested Ansible automation for the remaining LAN firewall prerequisite.
Extend REQ-0001/T07 with a separate, owner-run `deploy/server-setup.yaml`, using
interactive sudo via `--ask-become-pass`. It adds only the approved IPv4
`192.168.1.0/24` → TCP 8001 rule to the active `FedoraServer` zone, both immediately
and persistently. Check mode must not change rules; reapply must be idempotent;
missing/ambiguous inventory, an inactive zone and failed queries must stop setup.
Do not reload unrelated firewall state, change SSH rules or give ordinary
application deployment privileged access. Oscar runs the real privileged setup;
agents may test only isolated targets. This supersedes the handoff's manual
firewall-command step, not its owner-authorization boundary.

## Initial decisions — superseded where noted above

- Use a dedicated GitHub App identity for the agent, installed only on this repo.
  Do not use Oscar's GitHub login, personal token, or SSH identity for agent
  pushes and PR operations.
- Require PRs and successful CI for the bot. Oscar must retain the ability to
  push directly to `main` and merge despite failing checks. His bypass must not
  extend to the App; failed checks remain visible and failed.
- Keep the agent in the current local environment. A separate OS user or
  container without access to Oscar's SSH agent is not required now.
- Add CI on GitHub Actions, within GitHub Free allowances. Small diagnostic
  artifacts are acceptable; hosted container images are not a prerequisite.
- Build application images locally and deploy manually over the existing local
  access path. There is no container registry today. Do not introduce one or
  automatically deploy on PR, push, merge, or release.
- The home server is not reachable from the internet and is used only by Oscar.
  Brief downtime and pausing all application writes for a consistent backup are
  acceptable. Use a manually invoked Ansible playbook with reusable roles and
  a production Compose stack, following the existing Telegram-bot deployments.
- Back up database and uploaded files, and verify restoration. A simple periodic
  backup is in scope; its destination, retention, and schedule remain to choose.
- Support application rollback after a failed deployment. Never automatically
  restore an older database or run an Alembic downgrade.
- Keep version selection manual at release time, as already agreed in
  [planning and releases](../development_processes/planning-history-and-releases-2026-10-03.md).

## Repository baseline

Observed in the local checkout, not verified on the home server or in GitHub
settings:

- No `.github/workflows/` files are present.
- `src/harness/commands/test.py` exposes unit, frontend, integration, and E2E
  suites. The harness already manages isolated PostgreSQL and Docker/Podman.
- The root `docker-compose.yml` builds locally, mounts source code, and starts
  the application with `--reload`. It is a development configuration.
- Upload storage defaults to `data/uploads`; the root application's Compose
  service has no dedicated persistent upload mount.
- `Dockerfile` uses `COPY . .`; production packaging must restrict its build
  context so local data, credentials, and harness artifacts are not included.
- `/ping` returns a static success response; it does not check dependencies.
- No Ansible application deployment, deployment backup, rollback, or GitHub
  webhook automation was found in this repository.
- The local Git remote uses SSH. A token supplied to `gh` does not change the
  authentication used by `git push`.

## Deferred GitHub identity and branch-policy design

This section records the deferred App proposal, not the authentication policy
for the approved local/main cycle.

Use App installation tokens, which expire after one hour, rather than App user
access tokens acting on Oscar's behalf. Install the App only on this repo.

| Repository permission | Access | Purpose |
|---|---|---|
| Metadata | Read | Basic repository access |
| Contents | Write | Publish working branches and commits |
| Pull requests | Write | Open and update PRs |
| Actions / Checks | Read only if needed | Read CI results and logs used by the chosen commands |
| Workflows | None normally | Separate explicit authorization for workflow changes |
| Administration, Secrets, other permissions | None | Outside the bot's responsibilities |

Oscar authorizes App registration, installation, and branch settings himself.
The ordinary bot token cannot administer these settings. Workflow edits require
an explicitly approved bootstrap/update path; do not silently add Workflows
write permission to the normal identity.

Use an isolated `gh` configuration and explicit App authentication for both
`gh` and HTTPS Git operations. Missing or expired bot credentials must fail
without falling back to Oscar's login, SSH agent, or credential helper. Do not
change his global Git/CLI configuration. Keep private keys and tokens out of
Git, remote URLs, command logs, artifacts, and the conversation.

This is an authentication convention, not an OS security boundary: the agent
still runs in the same local environment. Do not claim that personal credentials
are technically inaccessible.

App permissions alone cannot restrict writes to working branches or distinguish
opening a PR from merging it. Enforce the desired policy with branch protection
or a ruleset: require a PR, Oscar's review, and CI; exclude the App from bypass;
give Oscar a bypass that also permits direct pushes, not just PR merges.
Do not grant broad write-role bypass when an admin/owner bypass is sufficient.

**Free-plan prerequisite:** branch rulesets/protected branches are available for
public repositories on GitHub Free; private repositories require an eligible
paid plan. Repository visibility is still unknown. Verify it before promising
server-enforced bot restrictions. If unavailable, report the limitation and ask
Oscar to choose; do not upgrade, change visibility, or describe a local agent
rule as equivalent enforcement.

## CI within the free tier

Run tests on GitHub-hosted standard Linux runners, without production credentials
or access to the home server. Reuse `uv run harness` for environments and tests;
do not hand-start Uvicorn or replace real database tests with mocks.

- Run on PRs, pushes to `main`, and manual dispatch. Do not deploy from a workflow.
- Use locked Python/Node dependencies, the existing pre-commit checks, and the
  harness unit, frontend, integration, and E2E suites. Confirm the trigger matrix
  after measuring runtime; do not silently skip expensive or failing suites.
- Keep `GITHUB_TOKEN` permissions minimal and pin Actions to reviewed commit SHAs.
  Do not execute untrusted PR code through a privileged `pull_request_target` job.
- Cancel superseded CI runs, cache reusable dependencies, and avoid an unnecessary
  OS/version matrix. Never change a failed test into a green check for a bypass.
- Keep artifacts small: failure logs, reports, and selected screenshots with short
  retention. Do not upload whole local artifact trees, database dumps, secrets,
  or application image archives by default.
- No paid runner, storage overage, or billing configuration changes without
  approval. Check account-wide usage and current quotas before enabling jobs.

GitHub currently documents 2,000 included monthly minutes and 500 MB artifact
storage for GitHub Free; standard hosted runners for public repositories have
different billing treatment. Recheck the applicable limits at implementation.
CI artifacts are diagnostics, not the deployment source or the backup archive.

## Local build and manual deployment

Build a clean, explicitly selected commit with locked dependencies. Keep the
previous working image locally, label/tag builds by commit, and record the image
ID, configuration reference, and Alembic revision used for each deployment.
Do not depend on a registry, mutable `latest`, or whatever happens to be in a
dirty working directory. Transfer the image locally if the build machine differs
from the server, using the existing trusted access path.

Production Compose must run the built image without source mounts or reload,
retain uploads outside the image, and keep database/files separate from test,
work, showcase, and task-board storage. Keep runtime DML credentials separate
from the one-shot migration credentials. No test/dev login endpoints in production.

The manually invoked procedure should:

1. Build and run the applicable checks before downtime. Show CI failures and
   stop by default; Oscar can explicitly choose a local deployment override.
   The agent must not infer that permission from Oscar's GitHub bypass.
2. Lock deployments against overlap and verify the selected image, configuration,
   backup destination, and available disk space.
3. Stop all application writers, including any background work, and take a
   coordinated database/upload backup before migrations. Abort if backup fails.
4. Run migrations with the migration role and start the selected application.
5. Verify database/schema readiness, storage access, and a representative
   authenticated read through the real login path. `/ping` alone is insufficient.
6. Resume normal use only after success. On failure, roll back the application
   only when schema compatibility is known; otherwise stop and report recovery
   options. Record the outcome and keep the previous image available.

Ansible orchestrates these steps only when invoked by the operator. No CI job,
webhook, or timer may trigger deployment.

### Ansible roles and existing references

Local references inspected on 2026-10-03:

- `../devin-telegram-bot/deploy/deploy.yaml`: local Podman build from a clean
  working tree, commit-tagged image, save/copy/load over Ansible's SSH connection,
  archive cleanup in `always`, Vault-rendered configuration with `0600` permissions
  and `no_log`, instance-specific persistent volumes, and systemd user lifecycle.
- `../blog-bot/deploy/deploy.yaml`: the simpler local build/transfer and systemd
  user deployment. Prefer the newer bot's Vault and cleanup conventions.

Both currently keep tasks inline; no reusable roles were found in these deploy
folders. Use their conventions as a reference, without modifying those projects
or requiring their checkouts at deployment time.

Keep the Root GDR playbook thin: a reusable image-transfer role and a Root GDR
role for configuration and Compose rollout. Keep database-specific backup,
migration, readiness and rollback sequencing together; do not create a role for
every task. Inventory, variables and templates must keep host details separate
from application logic and namespace service, directory and volume names.

Build the explicitly selected clean commit locally and transfer the commit-tagged
image without a registry. Use Vault for deployment secrets, keep its password
outside Git, and suppress secret-bearing output and diffs. Do not copy Telegram,
Devin or Git-push credentials into the application deployment.

Confirm the server runtime and boot lifecycle before adapting the bot's Podman
and systemd user pattern to the multi-service Compose stack. Reapplying the same
build and configuration must preserve data and avoid unnecessary restarts,
backups or migrations. A new rollout must still take its coordinated backup.
Verify syntax, supported check-mode behavior and repeated application in a
disposable target; check mode must not build images or change the server.

## Backups and recovery

Start with PostgreSQL logical dumps and coordinated upload copies; restic is a
candidate for encrypted storage, not an already installed dependency. Stop the
application writers while capturing both. Do not copy live PostgreSQL data files
as a substitute for a valid database backup.

Include the configuration and securely stored secrets needed to restore the
service, database roles/grants or their reproducible setup, and build/schema
identifiers. If the selected task board moves onto the server, cover its database
and attachments separately; follow SQLite's consistent-backup requirements.

Before enabling a timer, choose schedule, retention, and a destination off the
server. A same-disk copy is useful for deploy recovery but does not cover server
or disk loss. Make backup failure and excessive backup age visible to Oscar.
Perform a restore into an isolated database/storage directory and verify the
application and uploaded images, without replacing live data.

Application rollback may be automatic within the manually invoked deploy when
checks fail and the previous image supports the resulting schema. Test that
compatibility; do not assume every Alembic migration is reversible. Stop after a
failed rollback instead of alternating images indefinitely.

Database restore is a separate, explicitly authorized recovery operation because
it discards later writes. Destructive migrations require a reviewed maintenance
and recovery plan. PITR/WAL infrastructure, high availability, and blue/green
orchestration are not required for this single-user setup.

## Implementation tickets

These are proposed work boundaries, not implementation started by this request.
Implement, verify, and commit each ticket separately. Review current files and
GitHub/server capabilities before starting.

| Ticket | Scope | Acceptance |
|---|---|---|
| REQ-0001/T01 | App identity and owner/bot branch policy | Bot-authenticated working-branch push and PR work; personal-credential fallback fails; direct bot push to `main` is rejected; Oscar retains direct-push/failed-check bypass. Report unsupported plan features rather than marking enforcement complete. |
| REQ-0001/T02 | GitHub Actions CI | Harness suites run from a clean checkout; a deliberate failing test fails CI; small diagnostic artifacts and budget controls work; no deploy or production secrets. |
| REQ-0001/T03 | Local production packaging | Image built from a selected commit; persistent uploads survive recreation; no reload/source mounts or private build-context data; separate runtime/migration credentials. |
| REQ-0001/T04 | Coordinated backup and restore | Writes paused during capture; failed backup blocks deploy; isolated restore recovers DB, files, and permissions; approved schedule/destination/retention documented before periodic activation. |
| REQ-0001/T05 | Readiness and smoke checks | Check DB/schema and storage, plus a real authenticated read; demonstrate failure with an unavailable dependency and no production dev-login shortcut. |
| REQ-0001/T11 | Selected-commit deployment artifacts | Build the selected Git snapshot rather than a dirty checkout; validate Linux/amd64, OCI/runtime revision and package version; save a private archive with immutable image ID and typed size/checksum manifest; reject corruption and existing output without mutation. |
| REQ-0001/T06 | Role-based Ansible deployment and safe application rollback | Thin manually invoked playbook follows the Telegram-bot conventions; reusable image transfer and application-specific Compose role; Vault secrets never appear in output; syntax/check-mode checks and repeated deployment pass in a disposable target without data loss or unnecessary restarts; records the chosen build, backup, and schema; simulated failed rollout restores a compatible previous image; incompatible schema stops recovery without automatic data restore. |

T01 precedes bot publication. T03, T04, and T05 precede T06; CI is the default
verification signal, with an explicit owner-only override. Test recovery scenarios
in disposable environments, never by damaging production or resetting showcase.
Update an appropriate feature manual when implemented, rather than creating a
manual for every ticket.

## Deferred alternatives and remaining inputs

Manual deployment is a scope choice, not a consequence of lacking a registry.
A dedicated self-hosted runner could build locally with outbound HTTPS only;
a local poller could detect successful builds. Neither is approved now. Do not
run untrusted PR jobs on the production server or add webhook tunnels/relays.

Before implementation, confirm repository visibility and applicable GitHub
features; server OS/architecture, Docker/Podman, running stack and access path;
backup destination, schedule, retention, and acceptable data-loss window.
Do not provision services or buy a plan to resolve these unknowns automatically.

## References

Verified during the 2026-10-03 investigation:

- [GitHub App permissions](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/choosing-permissions-for-a-github-app)
- [Installation tokens](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app)
- [Rulesets and owner bypass](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository)
- [GitHub Free usage allowances](https://docs.github.com/en/billing/reference/product-usage-included)
- [Self-hosted runner networking](https://docs.github.com/en/actions/reference/runners/self-hosted-runners)
- [GitHub CLI authentication environment](https://cli.github.com/manual/gh_help_environment)
- [PostgreSQL logical backups](https://www.postgresql.org/docs/current/backup-dump.html)
- [Restic backups](https://restic.readthedocs.io/en/latest/040_backup.html)
