---
id: REQ-0023
requested_on: unknown
title: Agent feedback, corrected reference cases and replayable evaluations
recorded_on: 2026-10-21
---

# Agent feedback and replayable evaluations

## Purpose and authority

Evaluation is a mandatory product capability, not an optional final test of the
agents. The GM must be able to mark a successful conversation, explain a partial
mistake, produce a corrected reference with LLM help and reuse it as a benchmark.
Agent changes must be compared against stable, replayable cases.

This records the additional 2026-10-21 requirement. Deterministic checks,
LLM judging and mixed evaluation are required. The workflow safeguards, ticket
decomposition and gating mechanics below are recommendations to implement and
verify, not authority for paid calls, board writes or production replay.

## User stories

- As GM, I leave positive feedback on a conversation worth keeping as a reference.
- As GM, I comment "everything was right except this" without marking all of the
  work as wrong or losing the original result.
- As GM, I ask an LLM to draft a corrected reference or checks from my comment.
- As a benchmark author, I require exactly one character with specified values
  and no unwanted side effects, rather than trusting a plausible final message.
- As a benchmark author, I combine exact checks with judging of prose and fidelity.
- As maintainer, I see whether a prompt, model, tool or other agent change improves
  the same cases, regresses them, or has not actually been evaluated.

## Existing behavior and boundaries

[REQ-0022](REQ-0022-configurable-world-agents-and-intake.md) specifies durable
conversations/runs, configuration versions and source/change evidence, but its
original acceptance testing did not define a user-facing evaluation lifecycle.
This request adds that mandatory lifecycle without duplicating run storage.

[Action replay](../features-implemented/action-replay.md) replays recorded UI/API
actions and can rebind created IDs. It does not evaluate a new agent's choices.
Reuse proven fixture/ID-handling infrastructure where suitable, not its
status-only assertions as proof of agent correctness. Coding-agent benchmark
skills are a different product and are not the in-site evaluator.
The [declarative browser-scenario decision](declarative-scenarios-evaluation.md)
remains unchanged: typed domain assertions are not a new general browser DSL.

## Required evaluation lifecycle

### Feedback and promotion

Capture positive feedback and free-form comments against an identifiable run,
turn or selected conversation range. Preserve the full original evidence and
which part received feedback. A positive mark can create a reference candidate;
it is not proof that every mutation or sentence was correct.

Promotion freezes input turns, clarification inputs, source revisions, relevant
world preconditions, actor permissions and agent/configuration identity.
When pre-run state or an attachment is missing, report that the case is incomplete;
do not pretend the post-run world is the original starting point.

A candidate can define exact assertions, an expected answer, judge rubrics, or a
combination. Existing expected behavior may be edited manually or with LLM help.
Keep source feedback, original outcome and corrected reference distinct.

### Correcting a mostly successful example

For a comment such as "the character was correct, but its name was wrong",
an LLM can propose the corrected name, reference prose and relevant checks.
It cannot rewrite the recorded execution to claim the original was correct.
A corrected expected world state is hypothetical until independently validated.

Recommended approval workflow: show a diff with the comment and supporting
source, run structural checks, and let the authorized author publish the new
reference version. Publication makes it eligible for a benchmark suite.
The correction LLM cannot publish its own ground truth or weaken assertions to
make a candidate pass. Unsupported corrections remain questions, not facts.

### Versioned cases and suites

A case version contains the initial fixture and actor, user turns and sources,
expected behavior, assertion/rubric versions and resource limits. A suite version
pins exact case versions. A result pins the suite, evaluated configuration/build,
source/tool schemas, execution mode, attempts and evaluator/judge configuration.
Editing a reference creates a new version; old results retain their meaning.

Use stable fixture aliases for identities and generated IDs. Normalize declared
volatile values such as timestamps without ignoring ownership, identity,
relationships or other correctness-relevant differences.
Style references sent to an agent and hidden benchmark answers are different
assets. Do not leak held-out answers into evaluated prompts.

### Exact, judged and mixed checks

Exact checks inspect persisted application state and the mutation trace, not
only the assistant's response. They can assert counts, fields, associations,
track/reputation values, authorized actions and absence of unrelated changes.

For example, with a labelled synthetic input asking for one character:

- Exactly one new character exists relative to the starting fixture, including
  draft/soft-deleted creations when checking for unwanted work.
- It has the expected name, world, owner and explicitly requested values.
- Unspecified existing objects and fields remain unchanged.
- A repeated request/retry did not create duplicate records or extra marks.

Use typed, bounded assertion types. Authoring a case must not enable arbitrary
SQL, Python, shell or unrestricted paths from the browser. Code-based custom
evaluators, if needed, are reviewed application code rather than uploaded code.
Do not require an identical tool-call sequence unless that is itself tested.

An LLM judge evaluates aspects such as fidelity, completeness and prose style
against a versioned rubric and evidence. Its output includes per-criterion
scores/verdicts, supporting passages and uncertainty, not hidden reasoning.
The judge may disagree with positive feedback; preserve that disagreement.

Mixed cases require exact checks and the selected judge criteria. A judge's
positive score must never override a failed permission/count/state assertion.
Report exact failures and subjective scores separately, not one average that
hides a critical failure. Validate judge output and bound correction attempts.

### Recorded replay versus fresh execution

**Recorded replay:** use saved model responses/tool requests against a reset,
isolated fixture to test orchestration, tool contracts and persisted results.
It makes no fresh evaluated-model call. A separately requested live judge call
is still paid model work and must be labelled accordingly.

**Fresh evaluation:** run the candidate prompt/model/tools on the same initial
fixture and user inputs. This tests current agent behavior, including decisions
and generated prose. It may incur inference charges. Multi-turn clarification
inputs are pinned or follow explicit supported branches, not invented by an
unrecorded simulated user.

Recorded replay does not prove a changed model/prompt improved. A fresh run is
not bit-for-bit deterministic merely because the fixture and seed are fixed.
Support repeated trials and retain every attempt, including failures, cost and
missing results; do not retry silently until a passing example is found.

## Isolation, security and operating policy

Every case/trial starts from its own fixture in harness-owned test resources,
with fresh world/run/workspace namespaces and controlled actor permissions.
Never run a benchmark against the source campaign, production or showcase.
Benchmark selection grants no broader access to private conversations/files.

Keep fixture/source permissions, private-by-default datasets and an explicit
export/redaction step. Personal notes/photos and credentials are not committed
automatically. Removing secrets must not silently remove an important assertion.
Each judge and correction model receives only authorized evidence, through a
separate read-only evaluation context without world mutation tools.

Persist fixtures and revisions needed for reproducibility. Missing/expired
material makes a run incomplete, not passed. No automatic permanent retention
cleanup is authorized. Dataset sharing/retention and quota choices remain gates.
Judge/correction models are configurable independently of the evaluated agent;
record provider/model/prompt versions and usage for each.

## Mandatory change evaluation

Relevant agent behavior changes include prompts, model/profile settings, tools,
context selection, transcription/preprocessing and orchestration. Each needs a
same-suite baseline/candidate comparison before it is accepted as verified.
Evaluator/rubric changes must also re-evaluate comparison baselines; old/new
scores from different evaluator versions are not directly comparable.

Run offline deterministic checks and recorded replays by default where possible.
Fresh inference and live LLM judging are explicitly opt-in and never automatic
paid CI. Establish a bounded approved local evaluation policy before running
them. If fresh evaluation is required but not approved/available, report the
model-quality gate as outstanding, not passed through mocked responses.

Reports distinguish pass, fail, error, skipped, unsupported and incomplete.
Show regressions/improvements per case, hard-check results, judge criteria,
trial variability, latency and available token/cost measurements. Missing usage
is unknown, not zero. Do not select an arbitrary success threshold or silently
change the suite/reference to approve a candidate.

## Ticket plan and verification

Follow the
[REQ-0020 verification contract](REQ-0020-world-history-and-reversible-changes.md#verification-contract),
including real persisted-state assertions, desktop/phone comparison for delivered
interfaces, scoped commits and thematic manuals. Significant changes use
`REQ-0023-Tnn.<type>.md`. Prototype feedback/reference/results surfaces before
implementation using the current atlas components and established process.

### REQ-0023/T01 - Parent: replayable evaluation is part of agent delivery

**Outcome:** promote feedback into stable cases, correct references, run exact/
judged/mixed suites and compare changes with trustworthy evidence.
**Acceptance:** T02-T09 pass and REQ-0022's final acceptance uses this system;
no claim of model improvement rests solely on replayed responses or mock judges.
**Verify:** the complete feedback-to-corrected-reference-to-comparison journey.

### REQ-0023/T02 - Conversation feedback and reference candidates

**Story:** I mark a good result and explain a local mistake.
**Depends:** T03 case model, implemented REQ-0022/T06/T08 conversation UI.
**Boundary:** scoped feedback services/UI and provenance, not bug-board reporting.
**Acceptance:** positive feedback and comment persist against the exact scope;
candidate promotion is idempotent, retains original evidence, checks source
access and flags unavailable preconditions; feedback does not auto-publish truth.
**Verify:** database and E2E turn/run/range feedback, duplicate submit, denied
access, reload, partial-success comment and desktop/phone captures.

### REQ-0023/T03 - Versioned case, suite and fixture contracts

**Story:** the same benchmark still means the same thing after configuration changes.
**Depends:** REQ-0022 run/artifact contracts; schema/fixture work can precede UI.
**Boundary:** typed cases/suites/results, immutable source/fixture references.
**Acceptance:** freeze pre-run state/actors, inputs and expectations; explicit
publication/versioning; stable ID rebinding; imports validate schema and rights;
missing sources produce incomplete cases; hidden references stay hidden.
**Verify:** real-database round trips, version changes, missing files, permission
fixtures and old-result immutability without a live model.

### REQ-0023/T04 - Deterministic state and side-effect assertions

**Story:** I can require exactly the expected character and no unwanted changes.
**Depends:** T03 and corresponding domain services.
**Boundary:** typed assertion evaluator and authoring controls, not arbitrary code.
**Acceptance:** counts/deltas, selected fields, associations, permissions and
unchanged objects are checked against persisted state plus mutation history;
temporary create/delete side effects cannot hide behind a correct final count.
**Verify:** known-good and intentionally wrong fixtures, extra/incorrect/deleted
characters, false success prose, ownership errors and unsupported assertion types.

### REQ-0023/T05 - Isolated recorded and fresh evaluation runner

**Story:** I rerun a suite without changing my campaign or mixing trials.
**Depends:** T03-T04, implemented REQ-0022/T06/T07.
**Boundary:** harness-owned fixtures/workspaces and durable evaluation attempts.
**Acceptance:** fresh initial state per trial, explicit replay/fresh modes,
checkpoint/retry deduplication, pinned clarification and bounded budgets;
no default paid calls, silent retry selection or use of production credentials
as permission to spend. Preserve failed/cancelled attempts and their evidence.
**Verify:** two identical replays, concurrent isolated cases, restart/cancel,
cross-namespace denial and provider-call counting in default offline execution.

### REQ-0023/T06 - Versioned LLM judging and mixed-case scoring

**Story:** I evaluate prose/fidelity while retaining exact correctness guarantees.
**Depends:** T04-T05 and implemented REQ-0022/T04 profile configuration.
**Boundary:** judge profiles, typed rubric/results, evidence selection and scoring.
**Acceptance:** configurable judge separate from evaluated agent; versioned
rubrics and outputs; exact failures cannot be overridden; invalid/uncertain
judging is visible; no world tools or hidden answer leakage to the candidate.
**Verify:** fixture judges including disagreement/malformed answers, hard-fail
plus high-score cases and budget errors; calibrate against human-labelled
positive/negative examples before accepting live judge scores as a gate.

### REQ-0023/T07 - LLM-assisted reference correction and review

**Story:** my comment becomes a proposed correction without erasing what happened.
**Depends:** T02-T04, T06 model access/validation conventions.
**Boundary:** correction draft services, diff/review UI and immutable case versions.
**Acceptance:** edit answer, expected state, assertions or rubric with provenance;
review shows original/comment/proposal; only an authorized author publishes;
LLM cannot silently weaken checks, alter source evidence or promote a result;
retain rejected proposals and distinguish hypothetical corrected traces.
**Verify:** wrong-name correction, unsupported invented facts, proposed assertion
removal, stale concurrent reference edit, denied publication and persisted review.

### REQ-0023/T08 - Comparison reports and mandatory change gate

**Story:** I see how each change performs against the same accepted references.
**Depends:** T05-T07.
**Boundary:** per-case results/comparison UI and documented development checks.
**Acceptance:** baseline/candidate pin the same suite/evaluator; show hard checks,
judge dimensions, repeated attempts, errors/skips, cost and latency; mismatched
versions are labelled non-comparable; thresholds need an explicit accepted
policy. Relevant code/prompt/model changes cannot claim verification without
required evaluation evidence. Ordinary CI never starts paid model work.
**Verify:** regression/improvement, missing baseline, changed rubric, unavailable
provider and hard-fail masked-by-average fixtures, plus desktop/phone inspection.

### REQ-0023/T09 - Seed cases, calibration and full evaluation journey

**Story:** evaluation catches concrete mistakes rather than only producing scores.
**Depends:** T02-T08, corresponding implemented REQ-0022/T09-T12 workflows;
does not depend on REQ-0022/T13, which consumes this evidence.
**Boundary:** permitted/synthetic benchmark fixtures, integration/E2E and manuals.
**Acceptance:** exact character-creation case, faithful handwriting, repeated
sheet synchronization, transcript prose and a mixed exact/style case have
reviewed expected outcomes. Deliberately broken candidates fail for the intended
reason. A positive-but-one-error conversation yields a corrected published case
without altering the original run. Sources are not automatically public assets.
**Verify:** feedback-to-promotion-to-correction-to-baseline/candidate journey,
database/evidence inspection, default offline isolation, opt-in live calibration
only with approval, and desktop/phone comparison. Record untested model quality.

## Integration and unresolved choices

The [frontend study](../../prototypes/bookkeeping-study/README.md) demonstrates
positive feedback, an editable corrected reference and exact-versus-judge
presentation. Its [code notes](../../prototypes/bookkeeping-study/implementation-notes.md)
explain why the local JavaScript comparison is not a production evaluator:
real checks must query persisted state and mutation evidence.
No model-quality score or benchmark result is established by the prototype.

This capability is mandatory for agent acceptance, not a later optional analytics
screen. Build the T03-T05 foundation alongside run/tool infrastructure rather
than waiting until all agent features are complete.
REQ-0022/T13 depends on this request's acceptance evidence; this request's T09
depends on the relevant intake workflows, not that final acceptance ticket.
This avoids a circular dependency and allows offline infrastructure first.

Confirm feedback granularity/default scope, publication permissions, minimal
assertion vocabulary, judge rubric/calibration and pass thresholds before their
owning tickets. The user has selected exact, judged and mixed evaluation; the
particular framework, judge model, repeated-trial count and spending policy are
not selected. Prefer existing harness and Haystack facilities where they fit;
do not add an external evaluation SaaS or auto-upload private examples.

No board registration, paid benchmark, source conversation export or production
mutation occurs while documenting this request. Retention/purge and dataset
sharing decisions remain explicit, not inferred from a positive-feedback click.
