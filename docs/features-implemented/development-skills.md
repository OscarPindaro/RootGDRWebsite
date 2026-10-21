# Development workflow skills

Twenty-nine opt-in commands support development, review, documentation and maintenance.

## What it does

| Command | Purpose |
|---|---|
| `/using-development-skills` | Choose direct execution or clarification and planning. |
| `/brainstorming` | Resolve consequential requirements and design questions. |
| `/best-practices` | Research a decision against current sources and project constraints. |
| `/create-test` | Define or implement observable regression and performance checks. |
| `/refactor` | Audit read-only, then implement selected maintenance batches. |
| `/resolve-merge` | Propose, apply and verify approved conflict resolutions. |
| `/staff-review` | Review requirements and code quality in an independent context. |
| `/phone-a-friend` | Obtain a second-model review and resolve findings in one response round. |
| `/roast-my-code` | Present the same review with humor, only when explicitly requested. |
| `/explain-diff` | Explain behavior and decisions, with optional visuals, quizzes and notes. |
| `/align-docs` | Check stale claims and maintain documentation using existing conventions. |
| `/simplify-stuff` | Simplify documents and instructions without losing requirements or references. |
| `/handoff` | Write a temporary continuation note for another conversation. |
| `/bro` | Restate an unclear explanation in plain language. |
| `/align-stack` | Check or migrate Python project tooling against the shared team standard. |
| `/align-upstream` | Check and deliver changes from a configured standards repository. |
| `/update-deps` | Update Python dependencies or hooks while preserving pin styles. |
| `/commit` | Commit the requested staged changes without attribution trailers. |
| `/changelog` | Add or derive release notes using the repository's existing tooling. |
| `/integrate-observability` | Apply the shared Python or TypeScript logging and telemetry contract. |
| `/design-audit` | Report UI consistency and accessibility findings without editing. |
| `/visual-design-principles` | Work within the target project's existing styling system. |
| `/mui` | Apply MUI 6+ guidance only to an existing MUI scope. |
| `/team-conventions` | Apply shared UI behavior where project rules permit it. |
| `/ai-agent-bench` | Compare Claude Code and Codex coding trials; Devin is unsupported. |
| `/eval-regression` | Check Claude Code/Codex skill behavior; Devin is unsupported. |
| `/plugin-feedback` | Record observed skill problems and assess proposed corrections. |
| `/retro` | Analyze scoped native conversation history directly, including Devin SQLite. |
| `/coach` | Suggest improvements supported by the user's interactive conversation history. |

A sufficiently specified implementation ticket authorizes its scope without a
second planning approval. An idea-only ticket or unresolved consequential choice
requires clarification and approval of the resulting plan. Feature intake
continues to accept incomplete proposals without authorizing implementation.

`/explain-diff --quiz` enables free-response questions.
`--record-understanding` retains confirmed clarifications, unresolved concepts
and skipped topics in an agreed project document. Both are optional, independent
of each other and do not block completion. Without requested notes, the
discussion stays in chat.

`/align-docs --check` reports without writing. Normal maintenance can correct
verified in-scope claims; `--clean` proposes a collection-wide cleanup before
editing. Structural changes and deletions require explicit approval.
`AGENTS.md` stays a short entry point for essential rules and links. Chronicles
are optional; existing specifications, manuals and decision records take
precedence over a new documentation layout.

`/handoff` uses a private temporary directory by default and captures current
work, verification, decisions, resource ownership and permission limits.
Temporary notes are local and not durable; another destination can be requested.
`/bro` changes the explanation only, without editing files or starting a quiz.

The maintenance skills retain the collaboration standards supplied with the
archive. `/align-stack check` reports differences without applying a migration.
Repository conflicts need an explicit decision. `/align-upstream` requires a
configured delivery ledger; this port does not create one or claim upstream
topics have been delivered.

`/changelog` detects existing release tooling before choosing its procedure.
Here it uses Towncrier fragments and non-consuming draft previews. The manual
`CHANGELOG.md` procedure is a fallback for repositories without a generator.
The user still chooses release versions and approves consuming builds.

The four UI skills are installed for collaboration on applicable projects.
They remain opt-in and do not select MUI, shadcn, new tokens or notification
patterns for Root GDR. Its frontend guide, established design and Italian
localization remain authoritative. Impeccable already provides broader design,
critique, audit and refinement workflows when requested.

The MUI skill stops if a supported MUI dependency is absent. Team palettes,
dimensions and English locale defaults are fallbacks, not project overrides.
Code and screenshot audit procedures distinguish findings from evidence that
still needs browser measurement or interaction checks.

The benchmark and behavioral-evaluation runners do not support Devin, including
models accessed through Devin CLI or subagents. Their agent choices remain
`claude` and `codex`. This limitation is separate from the optional provider
guidance in `/phone-a-friend`.

`/plugin-feedback` works independently, including for observations from Devin.
It records evidence and public decision reasons, not private model reasoning.
Reports do not authorize unapproved changes or paid evaluation runs.

`/retro` and `/coach` read native history directly through bounded, read-only
queries or file excerpts. They do not install DuckDB, ingest transcripts, enable
hooks or build another conversation database. Scope defaults to the current
project and last seven days. Saved reports require permission.

Devin history support was checked against the local SQLite schema and message
envelope keys without displaying transcript bodies. The shared procedure follows
the selected conversation branch, limits dates and text, excludes hidden
reasoning, and treats historical instructions as evidence rather than authority.
This history support does not add Devin to the benchmark/evaluation runners.

## How it is built

Each command is a `SKILL.md` under `.devin/skills/`, with `triggers: [user]`.
The workflow entry point owns shared communication and authority rules; the
other skills link to it. Existing repository conventions supply the testing
harness, documentation locations, commit rules and tracking integration.
`/implement-ticket` owns Vikunja operations; the general skills do not.

The staff-review skill includes a shared read-only review procedure. The
second-model workflow supports Devin model-pinned profiles or a fresh Devin CLI
session, plus Claude Code and Codex. It requires an approved model, scope,
permissions, deadline and cost limits, and preserves one response round.
It does not hard-code models or enable permission bypasses.

The instructions adapt the workflow, review, documentation, maintenance, UI,
agent-tooling and analytics groups from the supplied
`ai-utils-main.zip`. They use plain-prose questions and the project's concise
writing style. The source archive declares internal Circeus use only; this port
does not grant redistribution rights.

`.devin/shared/` retains the technical team standards, runtime examples and
their linked supporting references. Local workflow, writing and documentation
bridges preserve the previously agreed adaptations. The stack skill includes
the source preflight scripts and disposable-project fixture suite. These assets
are references for explicitly requested work, not always-on project rules.

The benchmark scripts include their transcript parser, monitor and dated
pricing snapshot. Automatic permission-bypass flags are removed, existing trial
worktrees are not replaced, and evaluation telemetry export is disabled.
The behavioral runner's optional `pydantic-evals`/Logfire dependencies were not
installed. No native-plugin catalog or Devin adapter is created by the port.

## Limits

These are agent instructions, not runtime enforcement. Unit checks validate
entry-point metadata and local links; they do not establish model compliance.
Native-history query tests use a disposable SQLite fixture to check project,
date, branch and visible-text selection, output limits and write protection.
No full retrospective or coaching analysis of real conversations ran.
Runner checks cover script syntax and accepted agent choices. The benchmark
rejects `--agent devin` before creating trial artifacts. No model trial or
behavioral evaluation ran; full runner execution remains unverified.
The stack preflight suite exercises disposable fixture projects offline.
Private-library runtime examples, dependency upgrades, migrations, live
telemetry and actual release operations are not verified by the port.
Independent verification and review still require explicit delegation approval.
Provider instructions were checked against local Devin documentation and CLI
help; no paid model sessions or Claude Code/Codex launches were tested.
The provider guidance is a procedure, not an automated runner or a security
sandbox; access restrictions must be checked before each approved run.
The port does not install other plugins, agents, hooks or external tools, and
does not enable automatic skill invocation.
