# World agents: research and design boundaries

Research checked on 2026-10-21. This records product decisions from the
bookkeeping brainstorming and technical recommendations, not implementation
approval, completed features, a final schema or live ticket state. No provider
inference, dependency installation, application changes or board operations
were performed.

## Confirmed product direction

- The first user is the GM. Bookkeeping comes before canvas; canvas is excluded
  from this work. Player-facing sharing is deferred, not implemented privacy.
- A world assistant can read, create, update and soft-delete through the same
  services as the application, never exceeding the corresponding user's rights.
- Notes intake accepts handwriting, transcripts and sheet screenshots.
  Handwriting preserves wording and structure, with syntax/grammar-only cleanup.
  Session accounts derived from speech use the user's notebook prose as style
  examples, without inventing facts or speaker identities.
- A sheet screenshot synchronizes clearly readable values, leaves unrelated
  fields unchanged, and asks about ambiguity. Re-uploading must not add marks
  twice. Synchronizing state differs from applying an advancement action.
- Event extraction, scene grouping and timelines are future LLM-assisted work.
  They supplement the prose and retain source evidence.
- Both human and agent changes need versions, soft deletion and restoration.
  Recovery includes one item and an entire logical agent run.
- One logical run is one user request and its resulting work, including
  clarification. Later requests in the conversation are separate runs.
- Ollama's hosted API is the intended first provider. Provider, endpoint, model,
  prompts and operating limits must be configurable. Future Claude/OpenAI
  connections must not require rewriting domain tools or stored conversations.
  Implementing every provider now is not required.
- Agent prompts and configuration need a management surface and versions.
  Agent work needs an isolated working-file workspace; arbitrary server file
  access and code execution have not been requested.
- REQ-0016 may be ignored for this work, as explicitly confirmed after the
  research. Its older delivery requirements do not constrain the new scope.

## Existing application constraints

`pyproject.toml` requires Python >=3.14 and has no Haystack or provider SDK.
PostgreSQL, SQLAlchemy, Pydantic and an async storage interface already exist.

- `src/backend/npcs/service.py` checks world/draft access in its services.
  Updates enforce locks and an optional expected version. Deletes currently
  purge image revisions and physically delete the NPC.
- `src/backend/concurrency.py` and `src/backend/db/mixins.py` provide optimistic
  concurrency, not recoverable content history. A reusable soft-delete mixin
  exists, but that does not make existing content deletion recoverable.
- `src/backend/images/service.py` provides image revisions, not complete
  document/relationship versions. Soft deletion must stop ordinary deletion
  paths from purging recoverable attachments.
- `src/backend/db/db.py` provides transaction-scoped sessions. Agent tool writes
  must commit independently of a long model conversation.
- `src/backend/filesystem/base.py` is storage abstraction, not a permission
  boundary. `_resolve` joins paths; callers must not expose it directly to an
  LLM as unrestricted file access.

## Provider findings

Ollama documents direct hosted calls to `https://ollama.com/api` and an
OpenAI-compatible endpoint at `https://ollama.com/v1`, with bearer API keys.
No local Ollama installation or model download is needed. Cloud API model names
come from its catalog; CLI `:cloud` names are not a universal API naming rule.
Its OpenAI compatibility is a subset, not a promise of identical behavior [1].

Current Pro pricing is $20/month with $60 of included monthly usage credits.
Usage is token-priced and plan/account conditions can change; a subscription
does not justify unlimited agent loops. Do not encode prices in domain logic [2].

The structured-output documentation explicitly says cloud structured outputs
are currently unsupported. This is documented status, not a live compatibility
test or a reason to reject Ollama. Local examples do not establish cloud support.
Function tools, ordinary JSON generation and schema-enforced responses are
different capabilities. Validate every proposed mutation with Pydantic and
domain checks, with bounded correction attempts rather than relying on a
provider's strict-schema guarantee [3].

Tools and vision depend on the chosen model and endpoint. A text/tool model
cannot be assumed to transcribe handwriting. No model's suitability for these
Italian samples was tested. Select a model with the required capabilities or
configure separate task profiles explicitly; never silently change provider.

### Transport candidates

Haystack's `OpenAIChatGenerator` against Ollama's hosted `/v1` endpoint is
one candidate. It exposes explicit credentials, base URL, model, timeouts,
retries and tool settings. Keep `tools_strict` off unless the endpoint is
verified to support it. This uses OpenAI's protocol, not OpenAI's hosted models.

The native `OllamaChatGenerator` is also viable in principle: its `url` is
configurable, and Ollama Python SDK 0.6.3 reads `OLLAMA_API_KEY`. However,
integration 7.0.2 has no explicit credential/header constructor parameter.
It relies on SDK environment behavior, which is less convenient for multiple
credential profiles. Do not mutate process environment per request [4].
The user explicitly accepts the native integration. Choose the transport from
capability/compatibility evidence; neither transport is an approved constraint.

A provider profile should distinguish service identity from protocol:
provider, adapter, base URL, model ID, credential reference, supported
capabilities and allowed generation settings. Credentials stay server-side,
outside exported prompts/history. Future Anthropic support may need its own
adapter; configurability does not mean every provider is interchangeable.
Profile editing belongs to trusted administrators, including endpoint validation
to prevent server-side request forgery or sending credentials to arbitrary hosts.

## Haystack findings and alternatives

PyPI reported `haystack-ai` 3.4.1 and `ollama-haystack` 7.0.2 during this
research. Their metadata declares Python >=3.11; the project uses >=3.14.
Metadata alone does not prove runtime or full dependency compatibility [4].

Haystack provides an Agent loop, chat-message serialization, typed tool
definitions, runtime state, streaming and hooks before/after model/tool work.
The released 3.4.1 Agent defaults to 100 steps and four concurrent tool calls.
Choose explicit lower budgets and serialize writes initially; do not share a
SQLAlchemy AsyncSession across concurrent tool calls [5].

Important version boundary: Haystack 3 removed `ToolInvoker`, agent-specific
breakpoints and `AgentSnapshot`. Mid-agent pause/resume is no longer supported.
Pipeline debugging snapshots remain, but are not durable application jobs or
content rollback. Older 2.x examples must not define the new architecture [6].

GitHub follow-up found active work in this area, but not a verified restoration
of mid-agent snapshots: [async pipeline resume PR #13105](https://github.com/deepset-ai/haystack/pull/13105)
was closed without merge, as was [Agent schema recovery PR #12990](https://github.com/deepset-ai/haystack/pull/12990).
Recheck the chosen release at implementation time; do not infer support from
a closed PR or commit hash alone. Durable orchestration remains a compatibility
spike, not a reason to abandon Haystack.

Comparison:

- **Haystack plus application persistence:** fits the user's preference and
  shared-service design. The application must own durable execution and undo.
- **LangGraph:** provides persistent graph checkpoints and stores. It is worth
  reconsidering if durable graph orchestration becomes the main requirement,
  but adds another orchestration model. Even its checkpointing needs idempotent
  side effects; it does not undo world database mutations automatically [7].
- **OpenAI Agents SDK:** documents SQLAlchemy/PostgreSQL conversation storage.
  This corroborates application/database-owned conversation history, but a
  session store is not a complete revision journal or run undo mechanism [8].

Recommendation: keep Haystack and one application persistence layer. Do not add
multiple orchestration frameworks or a vector database for initial bookkeeping.

## Recommended persistence boundaries

Use ordinary relational columns for ownership, ordering, relationships and
queryable state. Use schema-versioned JSONB for variable message/event payloads,
validated through Pydantic models at internal boundaries.

| Record | Purpose |
| --- | --- |
| Conversation | World, user/access boundary, ordered messages and logical runs |
| Message | Role, ordered content parts, attachment references and tool-call links |
| Run | Request, pinned configuration, lifecycle, budgets, attempts and outcomes |
| Run event/tool operation | Model/tool inputs, outputs, errors, timings and durable operation identity |
| Content revision/change | Before/after state, relationships, actor, run and operation |
| Artifact | Source or working file, immutable revision, ownership and provenance |

Keep full available request/response and tool history in protected storage,
not ordinary logs. Store attachment references rather than copying base64 images
into every message. Do not assume provider-internal reasoning is available.
Token streaming is progress, not committed content or proof of a successful save.

Separate the retained transcript from the smaller context sent to the model.
Version summaries and style examples with their source references. Preserve
tool-call/result pairing when compacting. Recheck access before loading history
or artifacts, particularly after membership changes.

Pin each run's prompt/profile versions, model identifier, generation settings,
style-example revisions, tool/schema version and application build. Editing a
prompt affects subsequent runs, not a run waiting for clarification. Record
requested/resolved model metadata when available; hosted aliases may change.

Distinguish historical inspection, offline replay with recorded responses,
continuing an interrupted run, and a new paid rerun. They are different actions.
A rerun must not automatically repeat writes against the live world.

## Durable execution and reversible writes

Use a persisted job lifecycle and a worker with a database lease/heartbeat,
rather than an in-memory FastAPI task. Start with one active writing run per
world; manual edits still need optimistic concurrency. Worker scheduling choice
remains a proposal; no Redis or separate queue service is required by this study.

Haystack hooks can persist messages and lifecycle events. Durable writes belong
in service transactions, not hooks alone:

1. Bind user, world and run in trusted application context, not model arguments.
2. Recheck current permissions and locks; require an expected version for agent
   updates even though today's general update contract permits omission.
3. Execute a short transaction covering the mutation, revision/change records,
   and durable operation result with a unique application operation key.
4. On retry of that operation, return the stored result instead of applying it
   again. Record the model tool-call ID separately; it is not a global key.

Persist model replies before invoking their tools. After a crash, reconcile
pending operations against their committed results before continuing. A logical
run can span several fresh Haystack invocations using persisted messages/state;
this is boundary-based continuation, not a saved Python execution stack.
Clarification should persist a waiting state and release the worker.

Do not claim exactly-once provider inference: a timeout can occur after the
provider charged for a response but before it was durably received. Enforce
limits across attempts, cancellation and restarts, not just each Agent instance.
Cancellation stops further work; it does not imply rollback of committed work.

For content recovery, use immutable snapshots of small domain records plus an
ordered mutation journal, including joins and attachments. Full application
event sourcing is unnecessary. All write paths need coverage, not only AI tools.

Run undo compensates committed mutations in reverse dependency order. Preflight
current permissions, versions and later references before applying it. Default
to no partial undo when a conflict is found; report the affected items instead.
An unchanged run-created item can be soft-deleted, but later human edits or new
references must block automatic removal. Restoring an old state creates a new
revision. Repeated undo must not repeat compensation. These are recommended
mechanics, not yet approved conflict-resolution UI.
Each mutating tool needs a recorded compensation using its captured prior state,
not merely a mathematical inverse. Reads need no inverse; later edits can make
compensation unsafe. Group related changes into a single journaled operation.

## Working files without server access

Offer artifact operations such as list, bounded read/search, create draft and
save new revision. Use opaque IDs or validated virtual paths within an explicitly
authorized conversation/world namespace. Reuse the storage abstraction behind
that boundary; the agent never receives raw storage credentials.
Recommend a private workspace per user/world/conversation with run-specific
scratch areas, not one shared directory for an agent definition. A separate
container is unnecessary for mediated artifact operations; arbitrary code
execution would require a distinct execution-sandbox design and approval.

Keep original uploads immutable, separate from transcriptions, summaries,
style examples and disposable scratch artifacts. Record checksums, MIME types,
limits and provenance. Retain referenced bytes while versions, trash or undo
can still need them. Explicit sharing is required; world membership alone must
not expose another user's private conversation artifacts.

Haystack's tool-result offloading already supports file stores and custom stores.
Its filesystem implementation returns absolute paths; use a scoped custom store
for application artifact references rather than expose host paths. Offloading
reduces context size but does not provide authorization, archival history or an
agent filesystem by itself [9].

No shell, arbitrary SQL, arbitrary URLs or code execution is needed. Uploaded
text and OCR are untrusted source data, not instructions granting permissions.
Prompt-injection defenses supplement service checks, never replace them [10].

Database transactions cannot atomically roll back filesystem writes. Stage
immutable bytes before committing their references; clean unreferenced artifacts
separately without deleting recoverable revisions. Run undo restores application
state, not provider charges or information already sent to an external service.

## Verification and specification follow-up

Before implementation, run a compatibility spike for the selected package
versions on Python 3.14. Provider fixtures should cover streamed tools, malformed
arguments, image messages and unsupported capabilities. Any live model checks
need separate explicit opt-in and use of credentials; none ran here.

Integration tests must prove crash-after-commit deduplication, restart while
waiting, access revocation, cross-world isolation, locked/version-conflicted
writes, idempotent screenshot synchronization, restoration with relationships,
attachment retention, and run undo blocked by subsequent changes.

Use the supplied Italian handwriting/transcript as acceptance material, with
user-approved expected facts and style examples. No speaker attribution can be
recovered reliably from the text alone. Fidelity and task quality remain untested.

The user explicitly permits ignoring
[REQ-0016](../features-request/REQ-0016-handwritten-draft-transcription-and-content-intake.md)
for this work. Do not carry forward its all-providers-at-once, four experimental
variants or file-access exclusion as requirements. Preserve the historical file;
the new specification should use the decisions recorded in this discussion.
[REQ-0017](../features-request/REQ-0017-service-accounts-and-api-credentials.md)
is for external bot credentials, not a prerequisite for an in-site assistant
acting as the authenticated user.

Open decisions: selected models and capability checks; worker/continuation
proof; artifact and conversation retention; configuration-management permissions;
undo conflict handling; scope of permanent purge and external side effects.
No permanent-purge tool or arbitrary external-action tool is recommended.

The subsequent specifications turn this discussion into bounded tickets:
[recoverable changes](../features-request/REQ-0020-world-history-and-reversible-changes.md),
[GM bookkeeping](../features-request/REQ-0021-gm-campaign-bookkeeping.md), and
[world agents/intake](../features-request/REQ-0022-configurable-world-agents-and-intake.md).
They distinguish confirmed product decisions from technical decision gates;
this research remains rationale, not a second backlog or an implementation.

## Sources

1. Ollama [cloud](https://docs.ollama.com/cloud),
   [authentication](https://docs.ollama.com/api/authentication) and
   [OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility).
2. Ollama [pricing](https://ollama.com/pricing) and
   [pricing change, 2026-08-31](https://ollama.com/blog/transparent-pricing).
3. Ollama [structured outputs](https://docs.ollama.com/capabilities/structured-outputs)
   and [vision](https://docs.ollama.com/capabilities/vision).
   GitHub follow-up: [documentation PR #15733](https://github.com/ollama/ollama/pull/15733)
   merged the cloud limitation note; [issue #12362](https://github.com/ollama/ollama/issues/12362)
   remained open with requests for updates through 2026-10-12.
4. PyPI version metadata and released wheels inspected in memory, not installed:
   [Haystack 3.4.1](https://pypi.org/pypi/haystack-ai/3.4.1/json),
   [integration 7.0.2](https://pypi.org/pypi/ollama-haystack/7.0.2/json),
   [SDK 0.6.3](https://pypi.org/pypi/ollama/0.6.3/json).
   Inspected Agent, OpenAI/Ollama generators and SDK authentication source.
5. Haystack [Agent](https://docs.haystack.deepset.ai/docs/agent),
   [State](https://docs.haystack.deepset.ai/docs/state) and
   [hooks](https://docs.haystack.deepset.ai/docs/hooks).
6. Haystack [3.x migration](https://docs.haystack.deepset.ai/docs/migration)
   and [pipeline breakpoints](https://docs.haystack.deepset.ai/docs/pipeline-breakpoints).
7. LangGraph [functional API: replay and idempotency](https://docs.langchain.com/oss/python/langgraph/functional-api).
8. OpenAI Agents SDK [SQLAlchemy sessions](https://openai.github.io/openai-agents-python/sessions/sqlalchemy_session/).
9. Haystack [tool-result offloading](https://docs.haystack.deepset.ai/docs/tool-result-offloading).
10. Anthropic [indirect prompt injection](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/mitigate-jailbreaks).
