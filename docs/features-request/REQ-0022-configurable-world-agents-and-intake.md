---
id: REQ-0022
requested_on: unknown
title: Configurable world agents, isolated workspaces and faithful content intake
recorded_on: 2026-10-21
---

# Configurable world agents and content intake

## Purpose and authority

The GM wants to ask an assistant to manage a world and to turn handwritten notes,
session transcripts or character-sheet images into useful campaign records.
It must use the same backend behavior and permissions as the human user, retain
their writing style and make its changes recoverable.

This specification captures the 2026-10-21 discussion and proposes bounded
implementation tickets. It authorizes no application execution, model spending,
board mutation, release or deployment. Board reconciliation has not occurred.
REQ-0016 is explicitly non-binding for this work; its four experimental variants
and all-providers-at-once requirement are not prerequisites. Preserve that
historical request, not its constraints.

## User stories

- As GM, I ask the world assistant to read, create, change or remove campaign
  content, and it can do at most what my account can do.
- As GM, I upload notebook pages and get linked world objects in my own prose,
  without manually retyping or approving every ordinary save.
- As GM, I upload a sheet and synchronize readable values, answer questions
  about ambiguous marks and undo a mistaken update.
- As GM, I turn a noisy transcript into an editable account like my notebook,
  without invented dialogue or speaker attribution.
- As administrator, I change agent instructions, model and operating settings
  without hardcoding them into domain services.
- As GM, I inspect what one request changed and undo it as a unit.
- As GM, I rate a useful conversation, correct a partial mistake and retain it
  as a replayable benchmark with exact checks, LLM judging or both.

## Baseline and related specifications

`src/backend/agents/` contains only a placeholder. No Haystack/provider dependency
is installed. Generic `tasks` provide status rows and an in-process
`spawn_background` helper; they do not provide durable, permission-scoped agent
jobs. Do not expose the existing generic task-poll endpoint as an agent-job API
without adding the corresponding ownership/access checks.

Domain behavior already lives in feature services. Images/files supply storage,
not an isolated agent workspace. Existing content deletes can physically purge
data. Agent write delivery depends on implemented recovery under
[REQ-0020](REQ-0020-world-history-and-reversible-changes.md), and new bookkeeping
tools depend on their corresponding
[REQ-0021](REQ-0021-gm-campaign-bookkeeping.md) features.
Do not independently rebuild either domain model inside `agents`.

## Confirmed behavior

### General world assistant

The assistant can perform the world's supported read/create/update/soft-delete
operations using shared services. User identity, selected world and logical run
are trusted server context, never authoritative model arguments. Check current
permissions, ownership, drafts and locks on every tool call, including reads.
An admin's capabilities are not silently lent to an ordinary user.

Prepare a capability matrix for all world operations, not a few sample tools.
Include content, conflicts/developments, factions, control, tracks, reputation,
relationships, files and recoverable world settings as their services become
available. Membership/invite operations need explicit recovery and external
side-effect analysis. Site administration, secrets and login credentials are
not ordinary world tools.

Ordinary requested writes do not require repeated confirmation. Ambiguity,
permission failures and conflicts still require a clear explanation or question.
The agent cannot silently unlock a document, select another world/provider,
purge history or invent a missing relationship.

### Intake modes

**Handwriting:** retain original ordered pages, raw transcription and any cleaned
version separately. Preserve wording, phrase order and style; cleanup is limited
to syntax/grammar. Do not turn prepared possibilities into occurred events.
Several pages about one entity can yield one object; several entities on a page
can yield several objects. Resolve against existing world identities before
creating duplicates. Flag uncertain words rather than invent campaign facts.

**Sheet synchronization:** identify the intended existing character/NPC and
update only clearly readable supported values. Leave absent fields unchanged.
Ask about ambiguous identities or marks. Apply absolute visible state, not
another advancement award. Re-uploading a sheet does not duplicate its marks.
Report changes and offer recovery. Character scope remains reputation and
optional damage/resource tracks, not a full digital character sheet.

**Transcript:** keep original text separately and generate an editable session
account using selected notebook examples for style. Distinguish previous-session
recaps, proposed/failed/completed actions, rules discussion and unrelated speech.
Four participants do not imply four identifiable voices in an unlabeled text.
Do not invent who spoke, dialogue, motives, chronology or precise dates.
Style examples are not evidence that their events occurred in this session.

Intake may create/update the corresponding world entities through shared tools.
Changes to conflict developments must be linked to evidence and the correct
story, not inferred from a place's name alone. The source is always available
for inspection. Full event extraction, scene grouping and timelines are deferred;
ordinary conflict development notes are not that future event system.

### Configuration and provider independence

Use Haystack, initially with Ollama's hosted API and the user's intended $20
subscription. No local model server or GPU is required. Native
`OllamaChatGenerator` and the OpenAI-compatible transport are both acceptable;
choose from a tested capability matrix, not a hardcoded architecture preference.

Provider, endpoint, model, credential reference, task instructions and operating
limits are configurable. Future Claude/OpenAI adapters must not require changing
world tools or conversation schemas; implementing those providers now is not
required. No silent fallback to another model/provider when a task fails.

Agent configuration has editable drafts and immutable versions, pinned per run,
including relevant tool/schema versions and selected style-example revisions.
Separate provider/credential settings from prompts and from hard authorization.
A prompt editor cannot grant tools or privileges beyond trusted policy.
Raw credentials are neither displayed in history nor passed to the model.

### Conversations, logical runs and recovery

Persist ordered messages, source references, model responses, tool calls/results,
errors and available usage. A logical run is one user request and its triggered
work, including clarification. A later independent request is a separate run.
One logical run may use several orchestration invocations or worker attempts.

Keep full retained history separate from context compaction. Persist a waiting
state for clarification and release the worker. Reload, multiple web workers
and application restart must not lose the job or repeat successful writes.
Cancellation stops further work but does not undo committed changes.

All mutating tools need recorded compensation. Link the run to the recovery
change set; per-item and whole-run undo use REQ-0020 services, not LLM-generated
reverse commands. Reads need no inverse. Preserve later edits and new references.
No ordinary tool permanently purges records, revisions or referenced bytes.

### Agent working-file isolation

Provide private workspaces with original sources, working drafts and run scratch
areas. The recommended boundary is user/world/conversation, with separate run
and agent-invocation scratch namespaces. Do not share one directory for every
instance of an agent definition.

Expose authorized artifact IDs or validated virtual paths, not host paths.
List/read/search/write-new-revision tools stay inside that boundary. Cross-user,
cross-world, traversal and symlink escape attempts must fail server-side.
Permission to read a world does not automatically reveal private conversations.

An execution container per agent is not required for mediated artifact access.
Arbitrary shell/code execution is excluded; adding it requires a distinct
sandbox design and approval. Artifacts are not a second source of truth for
world entities: only domain services commit canonical changes.

### Mandatory feedback and replayable evaluation

[REQ-0023](REQ-0023-agent-feedback-and-replayable-evaluations.md) defines required
feedback, case/reference versioning, LLM-assisted correction, exact persisted-state
checks, LLM judges and mixed scoring. It is part of agent delivery, not optional
post-delivery analytics. Positive feedback identifies a candidate reference;
it does not certify every action. Preserve original runs when correcting examples.

Capture the pre-run fixture, actor rights, input turns and source versions
needed to evaluate it again, not only the final conversation. Separate recorded
model replay from fresh candidate execution. Require relevant same-suite
comparisons for prompt/model/tool/orchestration changes; exact failures cannot
be cancelled by a favorable judge score. No benchmark mutates the live campaign.
Build evaluation infrastructure with run/tool storage, not only at T13.

## Research evidence and decision gates

See [the dated research](../development_processes/world-agents-research-2026-10-21.md)
for documentation, released-source inspection, alternatives and limitations.
No live model or Python 3.14 compatibility tests have run.

Ollama's cloud structured-output limitation is documented, not experimentally
proven for the future selected endpoint/model. JSON generation, function tools
and schema-enforced responses are different capabilities. Validate in the
backend regardless of provider guarantees; use bounded correction attempts.

Haystack 3's published removal of mid-agent snapshots does not settle the final
execution design. Recheck current releases/merged changes and test continuation.
Do not implement a second framework merely because a proposed PR is unmerged.
Persistence, external side-effect compensation and orchestration checkpoints
remain separate responsibilities.

Recommended design: PostgreSQL conversations/runs/events plus a durable worker,
short transactional tool operations, unique application operation keys and
captured prior state. Persist a model reply before executing its tools.
Do not claim exactly-once inference or that undo can reverse provider charges.
Choose worker/lease details after the compatibility proof.

## Verification contract

Every child follows
[REQ-0020's verification contract](REQ-0020-world-history-and-reversible-changes.md#verification-contract).
Use typed Pydantic boundaries and Alembic migrations with the two-role DB model.
Add a thematic manual update and `REQ-0022-Tnn.<type>.md` for significant changes.

Default tests use recorded/synthetic external-provider fixtures and real
application services/database. Live paid tests are separately opt-in, never CI
or a default integration run. A configured secret is not permission to spend.
Use only authorized, isolated test worlds; never import into showcase as a test.

Desktop/phone screenshots and prototype comparison are required for delivered
surfaces; backend-only tickets inspect their relevant user surface. Assert
persisted state after UI actions. Do not treat streamed tokens or success text
as proof of a committed mutation.

## Ticket plan

### REQ-0022/T01 - Parent: dependable world assistance and intake

**Outcome:** use the general assistant and three intake modes with configured
Ollama, inspect source/change evidence and recover a complete request.
**Boundary:** coordinate T02-T13; no implicit implementation within the parent.
**Acceptance:** selected compatibility decisions are recorded; all required
children pass, supported world operations have a capability/recovery matrix,
and real-model quality limits are explicit. REQ-0023 is implemented with
versioned, corrected references and exact/judged/mixed comparison evidence.
**Verify:** final matrix, T13 journeys and REQ-0023/T09; outstanding fresh-model
evaluation gates cannot be passed by replaying recorded responses.

### REQ-0022/T02 - Provider and orchestration compatibility proof

**Story:** the chosen model stack demonstrably supports the intended operations.
**Depends:** none; this does not authorize paid inference or deployment.
**Boundary/start:** Python 3.14, Haystack/SDK package versions, official released
source, minimal fixture-backed tools and relevant integration alternatives.
**Acceptance:** record tested versions, native/compatible transport choice,
auth/configuration, streaming/tool IDs, image messages, format behavior, context
limits, timeouts/retries and clarification/restart boundaries. Recheck GitHub
merge/release status. Distinguish executable proof from documented expectations.
**Verify:** disposable offline/fixture-backed tests and a reproducible report;
propose minimal optional live tests with model and spending scope separately.

### REQ-0022/T03 - Isolated source and working artifacts

**Story:** I can upload and retain source material without exposing server files.
**Depends:** REQ-0020/T03 file retention; T02 capability evidence.
**Boundary/start:** `files`, `filesystem`, image validation patterns and typed
artifact services; preserve originals and save derived revisions separately.
**Acceptance:** ownership, world scope, checksums, MIME/size bounds, ordered
pages and provenance persist; bounded reads/search work; virtual paths cannot
escape or reveal another namespace; interrupted uploads are safe; source bytes
remain available for recovery. Confirm retention/quotas before shipping.
**Verify:** real-storage integration tests for traversal, forged IDs, symlinks,
oversized input, byte preservation, deletion/restore and denied access.

### REQ-0022/T04 - Versioned provider and agent configuration

**Story:** I change instructions/model settings without editing domain code.
**Depends:** T02, T03 for versioned style examples.
**Boundary/start:** backend configuration/clients, agent profile/prompt services.
**Acceptance:** typed profile and prompt versions, secret references, capability
checks and explicit task settings; a run pins its configuration; credentials
never enter prompts/history/export; template inputs and endpoint destinations
are validated. Proposed initial editor permission is site administrator;
confirm whether world-level prompt overrides are needed before adding them.
**Verify:** configuration/revision tests, invalid endpoints/options, no secret
serialization, profile changes during a waiting run and unsupported capability.

### REQ-0022/T05 - Configuration management interface

**Story:** I inspect and edit agent settings and know which version a run used.
**Depends:** T04; prototype the surface before application UI implementation.
**Boundary/start:** existing admin/settings JinjaX/htmx patterns.
**Acceptance:** distinguish prompt drafts, published versions, model/profile,
credential availability and hard tool policy; editing never silently changes a
running request; restore configuration through a new version; forbidden settings
are not editable via forged requests. No API key appears in HTML or browser logs.
**Verify:** frontend/E2E create/edit/version inspection, failed saves and permissions,
persisted settings and desktop/phone comparison.

### REQ-0022/T06 - Conversations and durable logical-run execution

**Story:** my request survives reload/restart and can wait for my clarification.
**Depends:** T02-T04, implemented REQ-0020/T02 operation journal.
**Boundary/start:** `agents`, task infrastructure and shared transaction services;
decide reuse versus a scoped agent-job layer without rewriting unrelated tasks.
**Acceptance:** ordered durable messages/events, lifecycle and attempts;
request/change-set identity; lease/restart and pending-tool reconciliation;
clear distinction between clarification reply and new request; pinned config,
budgets across attempts and cancellation without hidden rollback. Progress
polling/streaming is ownership-scoped. Retain pre-run fixture/source references
for benchmark promotion. No shared DB session across tool calls.
**Verify:** PostgreSQL worker restart, duplicate submission, competing workers,
waiting/reply/cancel flows and crash after commit before result delivery.

### REQ-0022/T07 - Permission-checked world tools and compensation coverage

**Story:** the assistant can manage the selected world, but never exceed my rights.
**Depends:** T06, implemented REQ-0020/T06, corresponding REQ-0021 domain services.
**Boundary/start:** typed adapters over existing/new feature services; operation
inventory includes API, HTML, import, file and relationship behaviors.
**Acceptance:** every supported operation names its service, permission,
expected-version precondition, journal and compensation; no raw SQL, credentials
or LLM-supplied actor authority; reads filter drafts/trash; stale/locked writes
stop safely; batch failures report what committed. Membership/invite/external
side effects are implemented only after their reversibility gate is settled.
**Verify:** real-service permission matrix for owner/master/player/outsider,
revocation mid-run, forged world IDs, locked content, duplicate retries and
every registered mutating tool's compensator. No ordinary purge tool.

### REQ-0022/T08 - General assistant conversation and progress interface

**Story:** I request world work, answer questions and inspect the results.
**Depends:** T04, T06, T07; accept conversation/upload/progress prototype first.
**Boundary/start:** a world-scoped page or panel using current JinjaX/htmx;
select placement without redesigning the shell.
**Acceptance:** clear current world, profile and logical-request boundaries;
attachments, clarification, progress, failure/cancel and continuation; persisted
messages recover after reload; duplicate submit cannot repeat tools; source
links obey access rules. Expose stable turn/run/range identifiers for later
feedback integration by REQ-0023/T02; that ticket adds the feedback controls
without duplicating conversation storage. Ordinary writes do not demand
repeated confirmation.
**Verify:** fixture-backed E2E create/read/update/soft-delete, clarification and
restart, accessible keyboard/focus/live feedback, phone and desktop comparison.

### REQ-0022/T09 - Faithful handwriting intake and entity reconciliation

**Story:** notebook pages become linked campaign records in my own wording.
**Depends:** T03, T07, T08 and corresponding bookkeeping services.
**Boundary:** ordered source-to-transcription-to-entity workflow, not the old
four-variant REQ-0016 experiment.
**Acceptance:** preserve originals/raw transcription/cleaned text; entity
boundaries span pages; one page may describe several entities; existing objects
are matched safely rather than guessed from an ambiguous name; possible events
stay preparation; uncertain words are visible; output uses normal service writes,
provenance and recoverable change sets. No mandatory review for clear results.
**Verify:** user-approved Italian notebook excerpts and labelled synthetic edge
cases, reordered pages, repeated upload, ambiguous identity, partial failure,
style/wording comparison and API assertions for every created/updated object.

### REQ-0022/T10 - Character and NPC sheet synchronization

**Story:** I photograph a sheet and update the corresponding record safely.
**Depends:** T03, T07, T08, implemented REQ-0021/T04 and T12-T13.
**Boundary:** typed observation/patch results for supported identity/track/
reputation values; not an attributes, inventory or selected-moves importer.
**Acceptance:** apply clear absolute values, ask about ambiguous marks/entities,
leave cropped/absent fields unchanged; distinguish capacity from marked boxes;
do not advance reputation a second time; inconsistent visible sheet state is
flagged, not silently "corrected"; stale records require reconciliation.
**Verify:** repeated/cropped/blurred sheets, title/character ambiguity,
simultaneous human edits, exact persisted state, provenance and run undo.
Model-reading quality requires separately approved live acceptance evidence.

### REQ-0022/T11 - Transcript-to-session prose in the user's style

**Story:** a spoken session becomes a readable account like my notebook.
**Depends:** T03, T04, T07, T08 and implemented REQ-0021/T08/T14.
**Boundary:** original transcript, selected style examples, editable session
prose and evidence-backed entity/development changes; no scenes/timeline engine.
**Acceptance:** facts come from this source/context, style from the selected
examples; recap is not registered twice as a new event; proposals/failed actions
are not presented as completed outcomes; unknown speakers remain unknown;
paragraph/span provenance supports inspection; ambiguous outcomes ask rather
than invent. Existing prose is not overwritten merely by starting a rerun.
**Verify:** the local 18 October transcript after permission-safe fixture
preparation, noisy/synthetic cases, missing speakers/dates, style review,
persisted prose/links/developments and complete request recovery.

### REQ-0022/T12 - Change reports and whole-request recovery

**Story:** I see what a request changed and undo it or an individual mistake.
**Depends:** T08-T11, implemented REQ-0020/T07 recovery UI.
**Boundary:** run/change-set bridge, result summary, item-history links and
existing compensation services; no independent agent-only history mechanism.
**Acceptance:** report committed versus failed/pending actions and source
evidence; undo one logical request including clarification/attempts; include
creations, updates, soft deletions, relationships and track changes; later edits
or new references block unsafe undo; repeated undo is safe; partial/failed runs
remain recoverable. Explain that cancellation is not undo and charges remain.
**Verify:** mixed-operation E2E, restart before undo, permission revocation,
human edit after agent completion, repeated undo and persisted restoration.

### REQ-0022/T13 - Robustness, complete operation coverage and acceptance

**Story:** the assistant remains bounded and recoverable when input or services fail.
**Depends:** T02-T12 and implemented REQ-0020/T08, REQ-0021/T15 and REQ-0023/T09.
**Boundary:** adversarial/provider fixtures, operation matrix, backup/export
boundaries, replayable model-quality evaluation and thematic documentation.
**Acceptance:** bounded malformed-output correction, timeout/rate-limit handling,
token/step/time budgets across restarts, no silent provider fallback, malicious
OCR/tool text cannot grant permissions or escape workspaces; context compaction
keeps complete retained history and tool-result pairing. No default live calls.
Use REQ-0023's versioned suites to record exact and judged results; model-dependent
fidelity limitations are reported rather than hidden by mocks or recorded replay.
**Verify:** full handwriting/sheet/transcript/general-assistant workflows,
content and run restoration, source isolation, backup coverage, desktop/phone
captures and required benchmark evidence. Live calls require explicit approval;
missing required fresh evaluations leave acceptance outstanding.

## Dependency and decision gates

T02 proves compatibility before package/worker commitments. T03-T04 define
artifacts/configuration; T05 provides management, T06 durable runs and T07 tools.
T08 provides interaction; T09-T11 implement distinct intake modes; T12 exposes
shared recovery; T13 verifies the combined result. The parent cannot close
while any required mode exists only as a mock demonstration.
REQ-0023's case/runner foundation accompanies T06-T07, with feedback and reference
review integrated into the UI. Its final journey precedes T13; it does not depend
on T13, so the acceptance requirements are not circular.

Recovery primitives and domain features can be delivered independently of
paid model testing. T07's complete capability matrix cannot be declared finished
until the corresponding bookkeeping services and compensators are implemented.
No subagent or parallel-worktree execution is approved by this dependency plan.

Model choice, credentials, per-run budgets, retention/quotas, conversation
sharing, prompt-editor permissions and worker continuation are explicit gates.
Conservative proposed defaults are private conversations, administrator-managed
provider configuration and no permanent purge; obtain the owner's decision
before making irreversible retention or external-action choices.

Source documents and account configuration contain untrusted data. Do not load
notebook contents as policy or expose server secrets through prompt templates.
Persist only available provider metadata; do not promise hidden model reasoning
or deterministic reproduction of a paid rerun.

## References and registration limits

Use the [research](../development_processes/world-agents-research-2026-10-21.md),
[recovery specification](REQ-0020-world-history-and-reversible-changes.md),
[bookkeeping specification](REQ-0021-gm-campaign-bookkeeping.md),
[external client conventions](../clients.md) and [testing guide](../testing.md).
The bookkeeping specification lists local source evidence; originals have not
been moved, uploaded or added to Git by this planning work.

[REQ-0017](REQ-0017-service-accounts-and-api-credentials.md) covers external bot
credentials, not a prerequisite for an assistant acting as the signed-in user.
No live board IDs are assigned here. Reconcile existing tickets, including
older intake entries and friend-feedback bugs, before registering new tasks.
Do not move canvas cards, close REQ-0016 or overwrite current ticket progress
as a side effect of recording these specifications.
