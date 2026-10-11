---
id: REQ-0016
requested_on: unknown
title: Handwritten draft transcription and content intake
recorded_on: 2026-10-11
---

# Handwritten draft transcription and content intake

## Request and motivation

Most of the user's writing happens on paper. People, descriptions of places,
sessions and stories are drafted by hand first. Retyping them is the bottleneck
between the notebook and the world.

The request is to photograph those handwritten drafts, upload the photos, and
have an AI with vision capabilities transcribe them **exactly**, one page at a
time, keeping the user's own wording and style. A second step turns a
transcription into the actual content document — an NPC, a person
(`personaggio`), a place, a session or a story.

The intended benefit: the paper draft stays the source of truth, and getting it
into Root GDR is a review of a faithful transcription instead of a full retype.

This is feature intake, not implementation approval, prioritization, release
selection or an implementation-ticket plan. The approach below is the user's
proposal. The user's preference between pipeline and agent is recorded in
"Current / desired behavior"; the remaining open points are listed at the end.

## Current / desired behavior

No AI or LLM capability exists today. `pyproject.toml` has no Haystack,
provider SDK or similar dependency, and `config.py` has no provider settings.
The only outbound integration is Google SSO. Uploads exist — `files` +
`images` for world/character/NPC/place pictures and `reports` for in-app
evidence — but nothing that reads a photo's content.

Desired workflow, confirmed by the user on 2026-10-11:

1. The user uploads scans of handwritten pages in the context of a world
   document, so the resulting content belongs to that world.
2. A vision-capable model transcribes each page verbatim: same wording, same
   style, same structure.
3. A cleanup pass fixes **only** syntax and grammar. It must not restructure
   phrases or reorder content.
4. The transcription is converted automatically into the matching content
   document (personaggio, NPC, luogo, sessione, storia) with its fields filled.
   The user does nothing else — the pipeline creates the object.
5. Later, not now: specific additional formats.

Legibility rule, confirmed by the user: when a word is hard to read, the model
guesses it. When it remains very unsure, it writes `[illeggibile]` in place of
the word rather than inventing content.

Unit of work, confirmed by the user: one upload is one draft. Three pages about
the same character become **one** `personaggio`, not three. One page describing
two characters becomes **two** objects. The split is therefore by entity, not by
page: the model has to find entity boundaries inside and across pages.

Conversation record, confirmed by the user: the full conversation of every run —
pipelines and agents alike — is stored so it can be replayed later. See the
aspects section for what "replay" has to mean for a pipeline, which has no chat
transcript.

Four variants must all be delivered **end to end**, not as a paper comparison:

- a Haystack pipeline that transcribes **one page at a time**;
- a Haystack pipeline that receives **all the images at once**;
- a Haystack **Agent with tools**, instructed to work one page at a time;
- a Haystack Agent with tools, instructed to proceed **as it pleases**.

Roles, confirmed by the user on 2026-10-11: the **Agent** is the preferred,
primary path, because the instructions/script will likely be modified later. The
**pipeline stays as a one-shot quick function**. The two paths differ in how the
document kind is chosen:

- the agent detects the kind itself;
- a pipeline cannot: the kind must be given to it, and the pipeline guesses
  `tint`/`animal` from the text.

A later expansion, not in scope now: chatting with the agent to change a result
or create another character directly.

Providers to support: Anthropic Claude, OpenAI, Ollama, and OpenAI-compatible
endpoints. The user has an Anthropic key today; the other providers must be
implemented in the same delivery, not deferred.

## Scope and constraints

- **In scope:** scan upload of handwritten pages scoped to a world; verbatim
  per-page transcription with vision models; a syntax/grammar-only cleanup pass;
  provider-agnostic configuration across the four named providers, all built in
  the same delivery; automatic creation of the matching content document, one
  object per entity; a stored, replayable conversation record for every run; all
  four pipeline/agent variants working end to end.
- **Explicitly deferred:** "specific formats" beyond the current document
  kinds (shape unknown); the choice of a dedicated handwriting-OCR step versus
  a pure vision-LLM approach.
- **Sandbox:** not needed for now (user, 2026-10-11). The agent's tools are
  expected to be typed calls into the app's own services, so the tool loop is
  the boundary. File access and code execution are out of scope.
- **Open research at pickup:** whether dedicated handwriting OCR is worth adding
  alongside the vision model, and whether an image pre-processing step that
  makes the handwriting easier to read is worth adding. Both are proposals; the
  user does not consider the pre-processing necessary.
- Language, confirmed: the notebook is Italian. Transcription must not
  translate, and the syntax/grammar cleanup is Italian-aware. Temperature and
  non-determinism are not a concern for the user. Sending the notebook to a
  hosted provider is not a privacy concern for now.
- Fidelity is a hard requirement: the pipeline writes exactly what was written,
  in the user's style. The only permitted rewrite is the syntax/grammar cleanup,
  which must not touch phrase structure. Unreadable words are guessed, and
  marked `[illeggibile]` only when the model is very unsure.
- Project rules apply unchanged: Pydantic models at boundaries, no `getattr`/
  `setattr`, secrets from environment/config never committed or logged, and
  tests that mock external providers (the project's testing guide already
  describes mocking LLM APIs).
- The Haystack MCP was not available in the intake session. Pipeline authoring
  at implementation time is expected to use it (see `AGENTS.md`).
- Naming note: this "Haystack" is the deepset-ai LLM orchestration framework.
  `docs/development_processes/planning-history-and-releases-2026-10-03.md`
  uses the same word for deepset's Reno-based release-notes process. The two
  are unrelated and should not be confused in tickets.

## Acceptance criteria

Observable outcomes. Items marked *(proposal)* are inferred, not yet approved.

1. A user can upload scans of handwritten pages against a world and get a
   transcription for each page.
2. The transcription reproduces the original wording and style. The cleanup
   pass changes only syntax and grammar; phrase structure is preserved. A hard
   word is guessed, and only a very uncertain one becomes `[illeggibile]`.
3. All four variants (two pipelines, two agent instruction modes) work end to
   end on the same uploads, each producing the content object. The agent detects
   the document kind itself; a pipeline is given the kind it must create.
   *(confirmed)*
4. Provider configuration supports Claude, OpenAI, Ollama and an
   OpenAI-compatible endpoint, selectable without code changes, all implemented
   in the same delivery. *(confirmed)*
5. The matching content document is created automatically from the
   transcription, with its fields populated, and the user performs no further
   action. *(confirmed)*
6. Provider credentials are never logged or committed, and provider calls are
   the only new outbound integration. *(proposal)*
7. Automated tests mock the providers; only an explicitly opt-in
   `external_integrations` test may call a real endpoint. *(proposal)*
8. One upload produces one object per entity: three pages about one character
   yield a single `personaggio`; a page describing two characters yields two
   objects. *(confirmed)*
9. The full conversation of every run, pipeline and agent alike, is stored and
   can be replayed later. *(confirmed)*

## References

- [In-app reporting and reproduction](REQ-0014-in-app-bug-reporting-and-reproduction.md)
  — the existing upload/evidence precedent (`docs/features-implemented/report-panel.md`).
- [Image handling](../features-implemented/image-history.md),
  [`live-image-editor.md`](../features-implemented/live-image-editor.md)
- `src/backend/files/`, `src/backend/images/` — storage and ownership model.
- `src/backend/content/constants.py` — `ContentKind` (personaggio, npc, luogo,
  sessione, storia, pagina) and the tint/animal/shape vocabulary a conversion
  would have to fill.
- `src/backend/reports/` — a feature that already stores uploaded captures with
  a checksum and metadata.
- [External clients](../clients.md) — the documented pattern for outbound
  service clients and their settings.
- [Testing](../testing.md) — existing guidance on mocking LLMs and the
  external-integrations marker.
- [Planning board and request tooling](REQ-0012-planning-and-release-tooling.md)

## Aspects considered

Raised while refining the request. Each item is marked *(decided)* or *(open)*.

### Input and accuracy

- *(decided)* **Language:** the notebook is Italian; transcription must not
  translate and the syntax/grammar cleanup is Italian-aware. Mixed dialect or
  non-Italian fragments are left alone.
- *(decided)* **Determinism:** temperature and non-determinism are not a concern
  for the user.
- *(decided)* **Pre-processing:** a step that makes the handwriting easier to
  read (rotate, deskew, contrast, downscale to the provider's limits) is a
  proposal to look into. The user does not consider it necessary.
- *(open)* **Page order:** with several pages merged into one object, the order
  has to come from somewhere — upload order, filename, or the model.
- *(open)* **Image limits:** providers differ in max image bytes and images per
  request, which constrains the "all images at once" variant.

### Object creation

- *(decided)* **Kind detection:** only the agent detects the kind. A pipeline is
  given the kind it must create.
- *(decided)* **tint / animal:** the pipeline guesses them from the text.
- *(open)* **shape and session date:** places carry a fixed `shape` and sessions
  a real date (REQ-0007); how those are chosen is undecided.
- *(open)* **Markdown and mentions:** bodies are Markdown with `@` references to
  existing content. Should the pipeline auto-link names it recognises, at the
  risk of wrong links?
- *(open)* **Draft state:** creating objects as drafts (`is_draft`) would keep
  them out of the world until reviewed, but the user asked for no extra step.
- *(decided)* **Duplicates:** a run id and a dedup rule are accepted as needed.
- *(open)* **Provenance:** a link from the created object back to the scans it
  came from, and whether re-uploading a corrected page updates the object or
  creates a new one.

### The conversation record and replay

- *(open)* **A pipeline has no chat:** "the conversation" for it means the
  per-step inputs and outputs, not messages. The recorded shape has to cover
  both a pipeline run and an agent run.
- *(open)* **What is stored:** prompts, model responses, tool calls, image
  references, timings, token usage, errors.
- *(open)* **Replay semantics:** re-run against the same inputs, or re-open the
  saved transcript? LLM output is not deterministic, so a true replay needs
  recorded responses rather than a re-call.
- *(open)* **Retention** of that store.

### Agent tools and sandbox

- *(decided)* **No sandbox for now.** The agent's tools are expected to be typed
  calls into the app's own services, so the tool loop is the boundary. File
  access and code execution are out of scope.
- *(open)* **Guards:** write confirmation, step/call budgets to stop a runaway
  loop, and what the agent may read (other worlds, locked or draft documents).

### Operations

- *(open)* Cost and rate limits per run; a cap and a visible cost per run.
- *(open)* Provider capability differs: Claude and OpenAI vision are strong,
  Ollama's local vision models are much weaker. "All four in one go" has real
  variance.
- *(open)* Where the scans are stored (the `files` table, a new intake table),
  and their retention after transcription.
- *(open)* Synchronous versus background job, progress for a multi-page run,
  cancel, and retrying a single page.
- *(open)* Testing without keys: recorded provider fixtures plus one opt-in live
  test.
- *(open)* Who may run intake, and whether the created object follows the normal
  ownership and draft policy.
- *(decided)* **Privacy:** sending the notebook to a hosted provider is not a
  concern for now.

## Open questions

Deliberately unresolved. The user asked to record them now and decide at
implementation time.

**Pipeline path**

- The pipeline is given the kind, so its upload surface needs a
  personaggio/NPC/luogo/sessione/storia selector. Exact wording and placement
  are undecided.
- How the pipeline guesses `tint`/`animal`, and what it does when the text gives
  no cue (defaults, or leave empty for the user).

**Object creation**

- **shape and session date:** how places pick a `shape` and sessions a real date
  (REQ-0007).
- **Markdown and mentions:** whether the pipeline auto-links names it recognises
  to existing content, at the risk of wrong links.
- **Draft state:** whether created objects are drafts (`is_draft`) so they stay
  out of the world until reviewed, against the "user does nothing" requirement.
- **Provenance:** whether re-uploading a corrected page updates the object or
  creates a new one, and whether the scan-to-object link is stored.
- **Page order:** with several pages merged into one object, whether the order
  comes from upload order, filename, or the model.

**The conversation record and replay**

- **Replay semantics:** re-run against the same inputs, or re-open the saved
  transcript? LLM output is not deterministic, so a true re-execution needs
  recorded responses rather than a re-call. A proposal on the table: store one
  run record and treat replay as re-opening it, with re-execution as a separate
  action.
- **Run-record shape:** a Haystack pipeline is a DAG, not a chat, so the stored
  record has to cover per-step inputs/outputs for a pipeline and messages/tool
  calls for an agent.
- **What is stored:** prompts, model responses, tool calls, image references,
  timings, token usage, errors.
- **Retention** of that store.

**Accuracy and input**

- **Cleanup mechanics:** whether the raw transcription and the cleaned text are
  both kept, and whether the `[illeggibile]` markers survive the cleanup pass.
- **OCR / pre-processing:** whether dedicated handwriting OCR or an
  image-enhancing pre-processing step is worth adding. Both are proposals; the
  user does not consider them necessary.
- **Image limits:** provider differences in max image bytes and images per
  request, which constrain the "all images at once" variant.

**Agent**

- **Guards:** write confirmation, step/call budgets to stop a runaway loop, and
  what the agent may read (other worlds, locked or draft documents).

**Operations**

- **Providers:** which model is the default in development and on the mini
  server; is Ollama reachable on the LAN; how the four providers are configured
  (per-user or server-wide).
- **Long jobs:** synchronous versus background/queue execution, retries, partial
  results, and whether intermediate transcriptions are stored.
- **Cost and rate limits** per run; whether a cap and a visible cost per run are
  needed.
- **Scan storage:** the `files` table versus a new intake table, and retention
  after transcription.
- **Access:** who may run intake, and whether the created object follows the
  normal ownership and draft policy.
- **"Use my style":** what defines the style (existing documents as examples, a
  prompt, a style guide), and how consistency is kept across pages.
- **Future formats:** unknown; recorded as a stated future goal only.

## Tracking

Initial intake key: `REQ-0016/T01`. Registered in Vikunja project **Root GDR**
(project ID **2**), task ID **7**; title, project and description confirmed by
read-back on 2026-10-11. Classified `type:feature`, `area:backend`,
`area:frontend` (colour `#2563EB`) and `flag:open-questions`, because the
specification still has unresolved questions. No assignment, priority or release
is selected here. Current ticket state belongs in Vikunja.
