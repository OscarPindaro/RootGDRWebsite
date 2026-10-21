---
id: REQ-0020
requested_on: unknown
title: Recoverable world history, soft deletion and reversible change sets
recorded_on: 2026-10-21
---

# World history and reversible changes

## Purpose and authority

The GM must be able to recover from mistakes made manually or by an agent.
Versioning, soft deletion and restoration replace repeated approval prompts for
ordinary authorized agent changes. Both individual items and all changes from
one agent request must be recoverable.

This specification records the 2026-10-21 discussion. Ticket decomposition and
implementation mechanics are proposals, not authorization to execute the cycle.
No board state, priority, assignment, deadline or release is selected here.
IDs were allocated against repository metadata; reconcile with the real board
before registration. No board query or mutation was performed.

## User stories

- As GM, I can restore an NPC's prose or marked tracks without losing its history.
- As GM, I can recover a deleted story with its conflicts, links and attachments.
- As GM, I can undo one agent request even if it changed several objects.
- As GM, I am warned when undo would overwrite later work or break a new link.
- As a world member, I cannot use history or trash to bypass my ordinary rights.

## Existing behavior

Content has optimistic version numbers, draft visibility and locks. These are
not recoverable versions. `src/backend/db/mixins.py` has a soft-delete helper,
but the core content services use physical deletion. NPC deletion, for example,
purges image revisions before deleting the row. Images already have revision
history, including irreversible revision deletion.

Start with `src/backend/content/{models,policy,references,bulk}.py`,
`src/backend/concurrency.py`, the six content-domain services, world services,
and `src/backend/images/service.py`. Do not assume an existing version integer
or image-history dialog satisfies this request.

## Confirmed behavior

### Item history

Human and agent changes create recoverable versions. Include prose, identity,
marked/capacity values, associations and attachment/current-image references.
Who changed it, when, and which agent run caused it must be distinguishable.
Restoring an old version creates a new current version; it does not erase
intervening revisions.

Creation, updates, soft deletion, restoration and undo are recorded. Read tools
have no inverse. A mutating tool must capture enough prior state to compensate
its changes. Existing manual/API/import paths need the same coverage.

### Trash

Ordinary delete hides an item rather than purging it or its referenced bytes.
Restoration recovers it under the original stable identity and relationships.
Deleting a world must retain its recoverable contents rather than physically
cascade-delete them. Do not grant a restore operation ownership or membership
rights the current caller does not have.

Normal lists, counts, search, mentions, backlinks and exports must consistently
handle trash. Deleted items are not ordinary search results or link targets.
Permanent purge and automatic retention expiry are outside this delivery.

### One request, one change set

The application owns an ordered change set that can later be associated with
an agent run. One logical run is one user request, its clarification and tool
work; a later request in the same conversation is another run.

Each successful tool mutation belongs to its operation and change set. Failed
or cancelled runs can contain committed changes and must still be undoable.
Creation compensates by soft-deleting; updates restore captured prior state;
soft deletion compensates by restoration. Never blindly subtract counters or
overwrite rows: compensation depends on intervening changes and relationships.

Run undo must preserve subsequent work. A run-created item later edited by a
human or referenced by another operation cannot simply be deleted. Repeated
undo must not apply the compensations twice. Undo itself creates history.

## Recommended technical contract

The following are implementation recommendations to prove in T02 and T06:

- Versioned Pydantic snapshot schemas with immutable stored revisions; no full
  application event-sourcing rewrite. JSONB payloads are typed at boundaries.
- Short service transactions commit the mutation, revision and durable operation
  result together. Unique application operation keys deduplicate retries.
- Actor, world, operation and change-set identity come from trusted context,
  never an LLM-provided user ID. Existing request writers get their own context.
- Expected versions protect agent writes and all restoration/undo operations.
  Preserve existing API compatibility where omission is currently allowed.
- Default to all-or-nothing change-set compensation after conflict preflight,
  reverse dependencies, and a second check under transactional locks. Report
  conflicts without partial changes; selective recovery remains per item.
- Block new writes to a world while it is in trash. A dedicated recovery policy
  lets its authorized owner/admin find and restore it without making trash public.
- History/trash access is restricted to authorized editors as a proposed safe
  initial policy; confirm exceptions rather than expose former drafts or secrets.
- Stage immutable file bytes before committing references. Physical storage and
  PostgreSQL are not one transaction. Retain referenced bytes and separately
  clean only confirmed unreferenced staged objects.

The undo engine must work without an LLM and without a provider credential.
It must not require the original agent process to remain alive.

## Boundaries and compatibility

Cover worlds, characters, NPCs, places, stories, sessions, pages, their links and
image references. World settings/current-place and membership/invite database
changes need an explicit operation inventory; no membership bypass on recovery.
The mechanism must accept later faction, conflict and bookkeeping state adapters.

Do not automatically add new features to existing snapshots. Each new domain
must declare its snapshot schema, relationship dependencies and compensation.
Preserve stable IDs, existing published/draft behavior, nullable clearing,
optimistic conflict responses, document locks and image URL contracts.

Canvas/drawings, application users/login credentials, external email delivery,
provider billing and arbitrary external actions are excluded. Existing canvas
data and code must remain untouched. Undo cannot recall information already
sent to a provider or reverse an external charge.

Existing bundles remain readable. New snapshot/trash records must not leak into
ordinary content export; recovery export and backup are distinct from a content
bundle. Decide policy for deleted natural keys before changing import matching.

## Verification contract

Every child has a scoped local commit after verification, a human-sized manual
update and a significant-change fragment `REQ-0020-Tnn.<type>.md` when applicable.
Do not assign an application version or consume release fragments.

Use the supported harness: unit checks for pure snapshot/ordering rules,
integration tests with PostgreSQL for mutations and persisted state, frontend
tests for components, and E2E for recovery journeys. Mock only external providers.
Do not reset work/showcase or another agent's environment.

Each implementation ticket needs desktop and phone screenshots compared with
`prototypes/devin-prototype/`; backend-only changes capture their relevant
existing user surface and explain unchanged appearance. Visual changes also
need keyboard/focus, narrow-width and enlarged-text checks. Assert API/database
state after browser writes. Documentation-only planning has no rendered changes
and does not constitute implementation completion.

Useful existing suites: `tests/integration/test_content_concurrency.py`,
`test_access_policy.py`, `test_bulk.py`, `test_world_images_service.py`,
`test_references.py`, and the domain service tests. New selectors below describe
required tests, not files that already exist. Follow
[the frontend guide](../frontend_guide.md) before UI edits.

## Ticket plan

### REQ-0020/T01 - Parent: recoverable world changes

**Outcome:** item recovery and complete logical-run undo work across covered
domains without erasing history or bypassing permissions.
**Boundary:** coordinate this request; do not implement inside the parent.
**Acceptance:** T02-T08 pass, their decision gates are recorded, and one mixed
create/update/delete journey restores state and relationships with retained bytes.
**Dependencies:** no child starts until its stated prerequisites are satisfied.
**Verify:** review child evidence and run the combined recovery journey.

### REQ-0020/T02 - Revision and operation foundation

**Story:** I can recover an earlier state regardless of whether a person or
agent made the change.
**Boundary/start:** content/domain services, typed snapshots, operation/change-set
records, Alembic and the existing transaction/concurrency contract.
**Depends:** none; decide schemas and operation inventory before coding adapters.
**Acceptance:** existing records get a truthful baseline, not invented history;
covered creates/updates atomically record prior/result state and actor; a
rollback leaves neither mutation nor success journal; duplicate operation keys
return the same result without another mutation; timestamps and ordered IDs
are stable. Manual API, HTML and import writes cannot silently skip journaling.
**Verify:** PostgreSQL service/API tests including transaction failure and
two concurrent requests; inventory covered and intentionally excluded operations.

### REQ-0020/T03 - Retain recoverable files and image revisions

**Story:** restoring a document also restores a usable image or source attachment.
**Boundary/start:** `images`, `files`, `filesystem`, revision/delete routes.
**Depends:** T02.
**Acceptance:** ordinary revision/entity removal cannot purge bytes needed by
history; restoring the old image pointer serves its original bytes; failed
uploads do not create live references; staged-object cleanup cannot erase a
retained revision. Keep stable current-image URLs and existing upload limits.
**Verify:** image integration tests with real temporary storage, byte equality,
failure paths and cross-world reads; inspect the existing image-history UI.

### REQ-0020/T04 - Soft deletion throughout world reads and writes

**Story:** I can remove content from everyday use without destroying it.
**Boundary/start:** domain deletion, world cascades, palette/counts/references,
normal exports and import matching.
**Depends:** T02, T03.
**Acceptance:** trash is consistently excluded from ordinary surfaces; a trashed
world blocks ordinary access/mutation without removing membership/revisions;
references do not expose hidden/deleted titles; repeated deletion is bounded;
old bundles still import. Record natural-key behavior and migration/downgrade
limits before applying schema changes.
**Verify:** read-surface integration matrix, world/child deletion, import collisions
and no physical attachment or relationship loss.

### REQ-0020/T05 - Item restoration and permission-safe history APIs

**Story:** I can inspect revisions and recover an item or a prior version.
**Boundary/start:** recovery feature services/routes; existing access and lock rules.
**Depends:** T04.
**Acceptance:** original identity and links recover; restoring creates a new
revision; unauthorized, cross-world, stale and invalid-relationship requests
cannot mutate state or reveal private history; missing required dependencies
produce an actionable error rather than silently dropping links.
**Verify:** integration tests for prose, tracks, associations, images, ownership,
deleted worlds, former drafts and permission revocation.

### REQ-0020/T06 - Compensate a complete change set

**Story:** I can undo one request that changed several objects.
**Boundary/start:** operation journal and domain-specific compensation adapters.
**Depends:** T05.
**Acceptance:** mixed create/update/delete changes reverse in dependency order;
failed/partial runs remain recoverable; replaying undo is idempotent; later
edits or new references block unsafe compensation; a concurrent change after
preflight is detected transactionally; no partial undo under the proposed default.
**Verify:** real-database crash/retry, concurrent edit and dependency-cycle tests;
record the accepted conflict policy before exposing it in the UI.

### REQ-0020/T07 - History, trash and restoration interface

**Story:** I can understand what changed and recover it without database tooling.
**Boundary/start:** document actions, world recovery navigation and existing
Dialog/DocDetails patterns; do not redesign the site shell.
**Depends:** T05, T06; prototype and accept presentation before implementing it.
**Acceptance:** distinguish current/old/deleted states, show authors and change
groups, preview restoration consequences, display blocked recovery clearly,
and preserve focus/unsaved document edits. Restoring never pretends to be saved
before server acknowledgement. A change-set entry is usable without agent UI.
**Verify:** frontend and E2E item/trash/change-set recovery, API persistence
assertions, desktop/phone comparisons and failed-save behavior.

### REQ-0020/T08 - Coverage, compatibility and operational proof

**Story:** recovery remains dependable across restarts, exports and schema updates.
**Boundary:** adapter/route coverage matrix, snapshot evolution and documentation.
**Depends:** T02-T07.
**Acceptance:** every covered write entry point has recovery tests; snapshot
schema upgrades are explicit; backup includes referenced bytes and journal;
content bundles exclude private history by default; no permanent purge is
exposed as an ordinary operation. Record unimplemented administrative inverses.
**Verify:** mixed-domain E2E recovery, old-bundle round trip, restart tests and
fresh desktop/phone evidence; no live deployment or destructive recovery drill.

## Open decisions and references

An actual-frontend [planning study](../../prototypes/bookkeeping-study/README.md)
now explores item inspection, whole-request undo and later-edit blocking at
`/components/planning?view=history`. Its
[implementation notes](../../prototypes/bookkeeping-study/implementation-notes.md)
identify component reuse and code entry points. All state is simulated; this
does not implement or verify the recovery engine in T02-T08.

Decide snapshot granularity for autosave, history/trash access exceptions,
natural-key reuse, and administrative compensation before their owning tickets.
Do not introduce automatic expiry or silently drop older versions.

See [agent research](../development_processes/world-agents-research-2026-10-21.md),
[image history](../features-implemented/image-history.md),
[in-place editing](../features-implemented/in-place-editing.md), and
[world access](../features-implemented/world-access.md).
Feature manuals describe current behavior, not this request's future behavior.
