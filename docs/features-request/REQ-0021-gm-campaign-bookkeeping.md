---
id: REQ-0021
requested_on: unknown
title: GM bookkeeping for stories, conflicts, people, places and sessions
recorded_on: 2026-10-21
---

# GM campaign bookkeeping

## Purpose and authority

Make the site useful for preparing a game, finding information during play,
and recording what changed afterward. The first user is the GM, not players.
Preserve the user's prose and the existing atlas identity, JinjaX/htmx,
in-place editing and autosave. Canvas work is excluded from this cycle.

This records the 2026-10-21 brainstorming. Product decisions are distinguished
below from recommendations and decision gates. The ticket plan does not
authorize implementation, board writes, priorities, releases or deployment.
Request IDs are unique in the repository; board reconciliation is still needed.

## User stories

- As GM, I open "Ritorno a Borgo Mulino" and find its whole prepared situation.
- As GM, I distinguish "Modulo 4a e Documento 7b" from other conflicts and follow
  its actual changes across two sessions without rereading both accounts.
- As GM, I read an NPC's motives and moves and mark its tracks during play,
  including when that NPC represents a group.
- As GM, I distinguish an inn inside a clearing from an independent temple
  near two clearings whose factions want to control it.
- As GM, I maintain only useful character bookkeeping, not an entire digital
  playbook, and download that character's individual playbook.
- As GM, I keep a session account in my notebook prose, not mandatory event forms.

## Current behavior

Characters, NPCs and places are mostly identity plus Markdown documents. Their
models lack structured moves/tracks, playbooks, place containment and factions.
Stories have body, status, period and a many-to-many session relationship.
Sessions have prose, real date and in-world date. Mentions/backlinks exist.

Start with `src/backend/{characters,npcs,places,stories,sessions}/`, shared
`content`, `navigation.py`, world overview, `palette.py` and their neighboring
JinjaX pages. `src/backend/agents/` is an empty placeholder, not implemented AI.
Keep the existing story/session contract rather than replacing it.

## Confirmed domain decisions

### Stories and conflicts

A story is the whole prepared situation: clearing context, conflicts, people,
important locations and possible developments. It is neither a predetermined
plot nor only a retrospective. The example story is "Ritorno a Borgo Mulino";
the clearing is "Borgo Mulino"; "Modulo 4a e Documento 7b" is one conflict.
The earlier readings "Modulo 42" and "Documento 76" were incorrect.

A conflict belongs explicitly to one story. It may involve several places and
NPCs; its full text appears inside the story, not on each place page. Give it
stable identity and a direct anchor, but no separate conflict page is required.
Each conflict has:

- Initial situation: the prepared problem, written freely.
- Possible developments: conditional preparation, not established history.
- Actual developments: successive free-form notes, optionally linked to sessions.
- Active/resolved state and a resolution account explaining how it ended and
  what changed. Players need not succeed or intervene for it to resolve.

The initial situation is not overwritten as history accumulates. There is one
development history for a conflict, even when it involves several places.
Session accounts remain informal prose and may concern several conflicts.
Do not conflate a development note with the future structured event/timeline.

### NPCs and groups

The same NPC entry can represent an individual or a group. No individual roster
or automatic group-size calculation is needed.

Keep description and motivation in free-form prose. Optional "what they want"
and "what they would accept" belong to the NPC, not a per-conflict value table.
Do not add the previously proposed per-conflict role/negotiation fields.
Moves are ordered entries with a title and optional free-form description.
A title alone is valid. NPC moves do not require player-move dice mechanics.
Damage inflicted belongs in the quick reference; equipment is optional prose.
Existing NPCs must remain valid without backfilling invented stats.

Optional fatica, ferite, usura and morale tracks have distinct capacity and
marked state. The GM marks/clears them during play without entering the prose
editor. Marks persist across reloads and sessions; no automatic reset.
Track editing, including failure and concurrency, must obey domain permissions.

The user requests comparison of an open quick reference and a flippable card
inspired by the official NPC deck. Both use the same content and appear in the
NPC collection and relevant story conflicts. Both refer to the same saved NPC.
The user has not selected the winning production presentation.

### Places and factions

Places need a kind and optional geographic containment. An inn can be within a
clearing; a temple in a nearby forest is not forced inside either of two nearby
clearings. Do not interpret competing claims as multiple geographic parents.
Major/minor terminology alone does not express kind, containment and control.

Record a current controlling faction separately from claims in a story conflict.
A faction is a world entity, reusable across places and character reputation.
Abitanti is one shared rules category per world, not a faction per clearing.
Local inhabitants' control differs from no controller being recorded.
Do not automatically create a named faction for every community.

Proposed compact place context: list active conflicts by title/owning story,
linking directly to the story anchor, with no copied conflict text. This list
was suggested, not explicitly selected; decide in T02 before implementing T10.
Resolved conflicts remain in their stories, not an automatic place archive.

### Characters and reputation

Add playbook selection separate from the existing character title, and download
only that playbook's pages from the local source PDFs, not the whole anthology.
Inventory exact page boundaries; most entries being two pages is not a rule.

Interactive reputation is per character/faction, including Abitanti: rating
-3 to +3 plus independent prestigio and nomea marks. Manual editing and agent
sheet synchronization are supported ways to update it.

Character expansion is limited to optional damage/resource tracks and reputation.
Attributes, selected playbook moves, inventory and other sheet mechanics are
excluded. The proposed track set is fatica, ferite, usura and consumo where
applicable, not NPC morale; verify the actual sheets/rules in T11 before fixing
the character schema. Do not imply every character must configure every track.

Applying a reputation award and synchronizing a sheet are distinct operations.
Automatic threshold/leftover calculation is a recommended implementation, to
confirm against the rule examples in T13; the user's approval also allowed
using an agent to supply the values. Never advance a synchronized snapshot again.

### Sessions and source material

Keep session prose editable and stylistically like the user's notebook.
The original transcript is source evidence, not the session body. Its absence
of speaker labels prevents reliable attribution to the four real participants.
Do not invent dialogue, motives, dates, outcomes or identity mappings.
Agent transcription/generation and source attachment handling belong in the
agent specification. Future LLM event extraction, scenes and timelines are
deferred and must supplement rather than replace the prose.

## Compatibility and design boundaries

Keep world scoping, ownership, draft visibility, locks, optimistic versions,
mentions/backlinks, nullable clearing and existing URLs wherever possible.
GM-only use does not make published content private from current world members.
No new player visibility system is included.

New joins validate same-world membership and readable references, including
drafts. Deleting a related object must use the recovery contract rather than
silently lose a conflict, development or reputation row. New domains declare
snapshots and compensation adapters under
[REQ-0020](REQ-0020-world-history-and-reversible-changes.md).

Place kind taxonomy, faction membership UI, an affiliation badge, track limits,
and the location of quick-reference controls are not settled visual/API details.
Do not add configurable taxonomies or faction simulation as assumed requirements.
No automatic conflict escalation, location-control changes from prose, or session
mark resets. No maps/canvas, inventory engine, generated campaign facts or rules
automation beyond the selected reputation behavior.

## Evidence and acceptance material

Use the supplied examples, without committing copyrighted PDFs or private
transcripts. Local-only references are not portable fixtures:

- `/mnt/hdd1ntfs/Games/Root RPG/MSEDIZIONI-ROOT-GDR-Viandanti-e-Forestieri.pdf`:
  PDF pages 220-238, printed 219-237, clearing creation and Cuordiforesta.
- `/mnt/hdd1ntfs/Games/Root RPG/MSEDIZIONI-ROOT-IlGDR_ristampa2025.pdf`:
  printed pages 52-54 for reputation, 226 for faction selection.
- `/mnt/hdd1ntfs/Games/Root RPG/Playbooks/`: three source anthologies.
- Five notebook JPGs under the supplied Telegram `temp_data/`, named
  `PXL_20261021_192524179.jpg`, `PXL_20261021_192526938.jpg`,
  `PXL_20261021_192530604.jpg`, `PXL_20261021_192533917.jpg`, and
  `PXL_20261021_192539536.jpg`.
- `/home/oscar/Scaricati/Sessione root 18 ottobre.txt`: untracked local transcript.
- The attached official NPC deck images: identity/portrait front and compact
  tracks/motivation/moves/equipment reverse. Do not rely on `/tmp` attachments
  surviving; capture a permitted durable reference before prototype delivery.

T02 must prepare a reviewable fixture/evidence manifest from permitted excerpts
or clearly labelled synthetic data. Ambiguous handwriting needs user confirmation;
prototypes must not present invented resolutions as the user's played history.

## Ticket plan

Each child follows the
[verification contract](REQ-0020-world-history-and-reversible-changes.md#verification-contract):
passing tests, persisted-write assertions, desktop/phone comparison and a scoped
commit. New feature manuals describe actual delivery, not this specification.
Significant changes use `REQ-0021-Tnn.<type>.md` fragments.
T03-T14 declare and test new recovery adapters; T15 checks combined coverage.
No new backend feature ships while its writes bypass implemented recovery.

### REQ-0021/T01 - Parent: usable GM bookkeeping

**Outcome:** prepare, consult and update a story through two sessions, with
distinct conflicts, shared people/places and recoverable bookkeeping.
**Boundary:** coordinate T02-T15; no hidden implementation in the parent.
**Acceptance:** domain decisions and prototype choices are explicit; all selected
children pass; deferred features are not silently required for the basic journey.
**Verify:** the two-session journey and the T15 compatibility evidence.

### REQ-0021/T02 - Compare preparation and quick-reference prototypes

**Story:** I can choose how to consult NPCs and conflicts using realistic content.
**Depends:** none; no production writes or new domain schema.
**Boundary/start:** `prototypes/`, existing atlas references and frontend guides;
follow currently adopted prototype rules, not a pending REQ-0019 proposal.
**Acceptance:** open and flip versions share state/content; show both in the
collection and story; title-only/long moves and group NPCs work; tracks do not
accidentally flip the card; keyboard/touch, focus and reduced motion are covered.
Compare long stories, conflict navigation, place context and phone layouts.
**Verify:** static browser tests/screenshots, evidence manifest and explicit
user selection. Mock saves are labelled. No Impeccable redesign or extra
PRODUCT.md/DESIGN.md authority is implied.

### REQ-0021/T03 - NPC quick-reference data

**Story:** I can prepare individual/group NPC motives, moves, damage and equipment.
**Depends:** implemented REQ-0020/T02-T05.
**Boundary/start:** `npcs/{models,schemas,service,routes}.py`, content references.
**Acceptance:** optional ordered title/description moves, free-form motivation
and negotiation, damage and equipment round-trip; existing prose stays intact;
individual/group representation needs no roster; no per-conflict negotiation
fields; malformed, foreign-world and stale writes fail without partial changes.
**Verify:** service/API and recovery tests including blank optional fields,
long text, title-only moves and old NPCs.

### REQ-0021/T04 - NPC tracks during play

**Story:** I can mark/clear optional tracks without opening the prose editor.
**Depends:** T03, accepted T02 layout.
**Boundary/start:** NPC service and quick-reference JinjaX/htmx state.
**Acceptance:** independent capacity/marks for the four NPC tracks; invalid
counts and shrinking below current marks are rejected or explicitly reconciled,
never silently clamped; reload/session changes retain values; two appearances
use the same NPC/version; failed saves and stale views are visibly recoverable.
**Verify:** integration bounds/concurrency plus frontend and persisted E2E
marking in collection/story, including groups and locked/read-only states.

### REQ-0021/T05 - World factions and the Abitanti category

**Story:** I can name factions once and reuse their identities.
**Depends:** REQ-0020/T02-T05.
**Boundary/start:** a self-contained faction domain, world access/navigation
and typed references; select minimal name/description/body schema before coding.
**Acceptance:** one Abitanti category per world, idempotent seeding/backfill,
ordinary faction management, no automatic faction per clearing; same-world
validation and recovery prevent dangling place/reputation references.
**Verify:** real-database create/edit/delete/restore, cross-world IDs and
duplicate default creation; browser management and unchanged old worlds.

### REQ-0021/T06 - Place kind, containment and current control

**Story:** I can distinguish a clearing, its inn and an independent nearby temple.
**Depends:** T05.
**Boundary/start:** `places` models/schemas/service, world current-place behavior.
**Acceptance:** kind, optional containing place and current faction round-trip;
proposed single-parent containment is validated against self/cycles and foreign
worlds; missing controller differs from Abitanti; proximity/claims can remain
linked prose. Confirm the minimal taxonomy before fixing field validation.
**Verify:** clearing/inn/forest/temple cases, invalid graphs, nullable clearing
and recovery; competing claims never create duplicate temple records.

### REQ-0021/T07 - Story-owned conflicts and shared participants

**Story:** I prepare several distinct conflicts inside one story.
**Depends:** T03, T06.
**Boundary/start:** `stories` domain, typed conflict records/associations and
existing story/session validation; no independent conflict detail route required.
**Acceptance:** conflict has stable ID/order, one story, free-form initial and
possible-development prose, and links to several same-world NPCs/places;
duplicate/hidden references fail safely; old stories/body/session links survive;
no per-place or per-session conflict copies.
**Verify:** service/API migrations and recovery; two stories at the same clearing
keep separate conflicts; anchors do not depend on a mutable conflict title.

### REQ-0021/T08 - Conflict developments and resolution

**Story:** I follow one conflict's actual changes across several sessions.
**Depends:** T07.
**Boundary/start:** conflict/development services, optional session references.
**Acceptance:** append/edit/recover free-form actual developments independently
of possible developments; optional same-world readable session link; resolution
records a nonblank outcome/consequence account with resolved state; the initial
situation remains intact. Ordering/date semantics and reopening
are recorded before implementation, not inferred as timeline automation.
**Verify:** two-session history, no-session development, intervention-free
resolution, draft/foreign session rejection and complete restoration.

### REQ-0021/T09 - Story preparation and shared NPC quick references

**Story:** I open the whole preparation and consult an NPC without losing my place.
**Depends:** T02 selection, T04, T08.
**Boundary/start:** story/NPC pages and reusable editorial quick reference;
preserve existing DocDetails, editor and session selection.
**Acceptance:** distinguish introduction, context, conflicts, possible/actual
developments and resolution; direct anchors and compact navigation work; NPC
cards appear in collection and relevant conflicts using canonical data; card
controls retain focus and cannot flip during track interaction; long prose and
many conflicts do not overflow or require a fixed physical-card height.
**Verify:** frontend and two-session E2E authoring, keyboard/touch, simultaneous
NPC appearances, save errors, persistence and desktop/phone comparisons.

### REQ-0021/T10 - Place context and navigation

**Story:** I see what a place is, where it belongs and who currently controls it.
**Depends:** T02 selection, T06, T07; T08 if active-conflict context is selected.
**Boundary/start:** place collection/detail, related-place context and links.
**Acceptance:** kind/container/controller are understandable without a map;
the independent temple is not visually nested in both clearings; if selected,
active-conflict links name their owning story and contain no duplicated text;
resolved/hidden conflicts do not appear in that list. No automatic archive.
**Verify:** frontend/E2E clearing/inn/temple navigation, stale/deleted relations,
empty context, long names, phone and desktop screenshots.

### REQ-0021/T11 - Playbook catalog and individual PDF download

**Story:** I select a character's playbook and download just its own sheet.
**Depends:** REQ-0020/T02-T05; T02 for placement.
**Boundary/start:** character metadata, protected file-serving and a catalog
manifest; use the three local anthologies as source evidence, not Git payloads.
**Acceptance:** verify all playbook names/page ranges, duplicates and sheet
track semantics; selection is not the character title; download preserves all
pages belonging to that playbook and excludes other sheets; inaccessible/missing
assets fail clearly. Decide private deployment/redistribution and asset backup
before shipping; never publish a copyrighted anthology as a static asset.
**Verify:** manifest/page-count and PDF-open tests, authenticated API download,
invalid/foreign IDs, preserved selection and desktop/phone interaction.

### REQ-0021/T12 - Limited character damage/resource tracking

**Story:** I record useful damage/resource marks without a full digital sheet.
**Depends:** T11 rule inventory, reusable T04 track behavior.
**Boundary/start:** character models/services/pages; retain player-owner and GM
permissions even though the current user is GM.
**Acceptance:** only applicable optional tracks are enabled; capacity/marks
persist independently with manual correction and expected versions; no NPC
morale copied by default; no attributes, selected moves or inventory added.
Agent snapshot updates will reuse these services, not write directly to tables.
**Verify:** rule-backed track examples, owner/master/other-player access,
bounds/concurrency/restoration and manual marking across reload.

### REQ-0021/T13 - Character reputation and advancement state

**Story:** I maintain reputation, prestigio and nomea for each relevant faction.
**Depends:** T05, T12.
**Boundary/start:** typed character-faction state/services and compact UI.
**Acceptance:** rating -3..+3 and independent mark counts round-trip, including
Abitanti; decide automatic-award behavior against printed pp. 52-54; preserve
asymmetric thresholds, opposite-sign transitions, leftovers and both-track
effects. Exact sheet synchronization must not reapply awards or duplicate marks.
Migration never invents historical reputation for existing characters.
**Verify:** pure rule tests from manual examples plus integration/E2E manual
correction, repeated snapshot, stale writes, faction restore and boundary values.

### REQ-0021/T14 - Session prose with story/conflict context

**Story:** I record the session informally and find which conflicts changed.
**Depends:** T08, T09.
**Boundary/start:** session detail, existing story/session association and
development backlinks; keep real/in-world date semantics and pager.
**Acceptance:** prose remains the main editable account; related stories and
explicitly session-linked developments are navigable without requiring event
forms; missing dates/links work; hiding a draft hides its derived labels.
Session membership and development references do not silently rewrite each other.
Transcript generation, scenes and timelines are not implemented in this ticket.
**Verify:** two sessions affecting one conflict, one session affecting several,
existing session-selection regression and persisted authoring/screenshots.

### REQ-0021/T15 - Bundle compatibility and complete bookkeeping journey

**Story:** my campaign data survives export/import and the combined workflow.
**Depends:** T03-T14 and implemented REQ-0020/T08 coverage.
**Boundary/start:** `content/bulk.py`, references, palette, counts, seed fixtures
and thematic manuals; do not export private history as ordinary campaign content.
**Acceptance:** old bundles remain readable; new fields, associations and stable
conflict identity survive a documented new bundle version; ambiguous natural
keys are handled explicitly, not guessed; round trips do not duplicate factions,
NPCs or developments. Backup retains licensed playbook assets as permitted.
**Verify:** real-database old/new round trips and full prepare/play/update/resolve/
restore E2E, with shared NPC marks and desktop/phone prototype comparisons.

## Dependency and decision gates

T02 can explore before recovery is implemented; backend writes cannot.
T03-T04 and T05-T06 are separate slices, not permission for parallel agents.
T07-T09 combine them; T11-T13 add limited character bookkeeping; T14 preserves
the session workflow; T15 proves compatibility and the complete use case.
Each completed implementation child is tested and committed before dependent
work begins. No parallel worktree or subagent is authorized by this plan.

T02 selects the card presentation and whether to show active place-conflict
links. T06 settles a minimal place taxonomy and containment semantics.
T08 settles development ordering, dates and reopening. T11 settles exact sheet
inventory and distribution. T13 settles rule automation. Keep unresolved choices
in their owning ticket rather than silently inventing approved behavior.

## Related work and limits

[Story authoring](REQ-0010-story-and-page-authoring-design.md) and
[story composition](../features-implemented/story-composition.md) describe the
existing session selection and details panel; this request evolves their domain
meaning without reopening unrelated page-authoring choices.
[REQ-0019](REQ-0019-frontend-system-stability-and-workflow.md) owns active frontend
repairs and design-process decisions. Inspect accepted outcomes before UI work;
do not overwrite concurrent fixes or assume every proposal is adopted.
Use the [frontend guide](../frontend_guide.md),
[prototype process](../development_processes/prototyping.md) and
[agent research](../development_processes/world-agents-research-2026-10-21.md).
Neither the official deck's artwork nor its physical dimensions replaces the
existing site design system.
