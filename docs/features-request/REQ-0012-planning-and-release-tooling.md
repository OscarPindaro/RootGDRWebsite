---
id: REQ-0012
requested_on: 2026-10-03
title: Server ticket board, planning tooling and Markdown release notes
---

# Planning and release tooling

Approved as part of the 2026-10-03 infrastructure/document cycle. This request
owns the specification; Vikunja owns current backlog and ticket status. The
[planning research](../development_processes/planning-history-and-releases-2026-10-03.md)
records the earlier alternatives and confirmed choices.

## Boundaries

- Deploy Vikunja 2.6.0 as a separate server instance with SQLite, attachments and
  signing secret isolated from Root GDR and the local demonstrations. Reach it
  from the PC through SSH; keep the server listener on loopback.
- Create new owner/tooling accounts with dedicated privately stored credentials.
  Close public registration, mail and link sharing. Do not change existing local
  accounts or import demo projects. Retain Kanboard unchanged for comparison.
- Use Vikunja's API v2, whose schema was verified on the running 2.6.0 trial.
  Use a scoped token and typed Pydantic/httpx boundaries. Credentials never
  appear in command arguments, output, remote URLs, repository or artifacts.
- Provide list/show/create/move/close/comment and an idempotent dry-run import.
  No task deletion, Kanboard integration, two-way synchronization or new Root
  GDR database tables are required.
- Give requests stable `REQ-nnnn` IDs and frontmatter with `id`, `requested_on`
  and `title`. Ticket keys are `REQ-nnnn/Tnn`. Preserve H1–H7 and F1–F22 aliases;
  numeric IDs do not imply execution order, priority, application version or
  Alembic revision.
- Import only real tickets of the approved cycle. Inventory historical documents
  without importing or mass-renaming them. Distinguish explicit request dates
  from first Git recording/import dates when historical evidence is incomplete.
- Reimport creates missing tickets only; it does not reset board progress,
  ownership, relations or user-written descriptions. Duplicates are an error.
  Reconcile an ambiguous write timeout by reading before retrying.
- Close a ticket only with verified tests, desktop/phone evidence and review.
  Its outcome links the commit, specification, verification and thematic manual;
  do not manually mirror current board status in Markdown.
- Use Towncrier development tooling with Markdown fragments in `changelog.d/`
  and `CHANGELOG.md`. One significant user/operator change gets a note; internal
  exclusions are explained in the outcome. No custom changelog generator.
- `pyproject.toml` is authoritative for application version. Remove an independent
  npm application counter; expose version/build in backend and deployment
  metadata. Keep 0.1.0 for this cycle. Drafting notes does not publish, tag, bump
  or consume fragments; Oscar chooses the version at release time.

## Attachment tooling extension — recorded 2026-10-10

Oscar requested image-upload tooling after choosing Vikunja, not Git, as the
location of REQ-0015's visual references. Ticket key: `REQ-0012/T08`.

Add typed attachment metadata, `attach <task> <files>...` and `attachments <task>`
to the existing API v2 client/CLI. Stream uploads, verify persisted bytes by
read-back, reuse identical filename/content matches and reconcile ambiguous
writes before retrying. A 201 response containing per-file errors is not success.
Batches retain earlier verified uploads and report partial results on failure.
Use explicit local file paths, bounded errors and private token files; never log
credentials, delete attachments or silently expand a live token's permissions.

Acceptance: real disposable-board PNG upload/download and persistence across
restart; repeat upload produces no duplicate; missing task/file and denied scopes
fail safely; partial batch JSON identifies verified uploads; unit coverage for
ambiguous writes and corrupt read-back. Publishing or rotating the live scoped
token is a separate owner decision. No frontend changes are required.

## Tickets and acceptance

| Ticket | Boundary | Acceptance |
|---|---|---|
| REQ-0012/T01 | Isolated server Vikunja deployment | Real login, loopback listener, persistent data after restart, consistent backup/isolated restore, idempotent Ansible and no local demo changes. |
| REQ-0012/T02 | Request metadata and historical inventory | Unique typed IDs/dates/links; H/F aliases retained, unknown dates labelled, no live-state mirror or historical import. |
| REQ-0012/T03 | API v2 reading and creation CLI | Real isolated API tests, full pagination, minimal credential scope, bounded errors and human/JSON output without secrets. |
| REQ-0012/T04 | Move/close/comments | Correct project/view/bucket and done semantics, partial updates preserve unrelated fields, ambiguous retries do not duplicate writes. |
| REQ-0012/T05 | Import new cycle tickets | Dry-run is read-only; repeated imports preserve manual progress and descriptions; demo/history cards never enter the real backlog. |
| REQ-0012/T06 | Towncrier and version authority | Draft leaves files/version unchanged; fragment validation/aggregation and runtime build metadata work, without an actual release. |
| REQ-0012/T08 | Verified attachment uploads | Typed image upload/list, byte read-back, sequential retry protection, partial-batch receipts and scope denial on an isolated real board. |

Deploy and recovery sequencing follow
[REQ-0001](REQ-0001-github-ci-and-manual-deployment.md). The board is bootstrapped
before parallel implementation waves; the coordinator reviews and verifies every
integrated ticket. Test instances, ports, SQLite files and attachments are unique
per worktree and never reuse the demonstration volumes.
