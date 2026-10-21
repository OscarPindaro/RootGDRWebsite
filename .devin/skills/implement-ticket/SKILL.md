---
name: implement-ticket
description: Resolve one real Vikunja implementation ticket and its dependencies, implement its approved scope, verify it, and move it through the project's discovered workflow.
argument-hint: "<Vikunja task URL, task ID, or REQ-nnnn/Tnn> [next]"
triggers: [user]
---

# Implement ticket

Use the real Vikunja board as the authority for scope, dependencies and progress.
An invocation selects one ticket; it does not authorize executing every child of
an epic, changing priorities/assignees/releases, pushing or deploying. Read
`AGENTS.md` and the ticket's repository specification before changing code. Do
not automatically invoke other project skills or launch subagents/worktrees.

Use the [development workflow](../using-development-skills/SKILL.md) as guidance
for planning and verification; this skill owns all Vikunja operations. Picking
up a ticket authorizes its implementation when scope, expected behavior,
acceptance criteria and approach are sufficiently clear. Do not require a second
plan approval merely because the work is substantial. Inspect linked evidence
first; if consequential decisions remain unresolved or the ticket only records
an idea, ask in plain prose and obtain approval for the resulting plan before
implementation. Do not reopen decisions already settled in the specification.

## Resolve before starting

1. Verify the checkout and `git status`; preserve unrelated work and live artwork.
2. Read the existing Backlog CLI documentation in
   `docs/features-implemented/production-deployment.md` and command `--help`.
   Use `harness backlog` or the existing typed `BoardClient`; never Kanboard,
   example boards, automatic historical imports or a guessed task/project ID.
3. Use the documented loopback SSH tunnel and consolidated scoped token via
   `ROOTGDR_BOARD_TOKEN_FILE` / `--token-file`, or the default private controller
   file. Never print credentials, put tokens in argv, rotate tokens or expand
   permissions. Reuse an existing connection; close only a tunnel you created.
   Authentication/scope failures require owner help, not a new credential search.
4. Discover the real project, its views and buckets. Resolve the supplied URL/ID
   or exact stable key, and read the task plus comments with `show --json`.
   Duplicate keys or ambiguous selectors require clarification, not guessing.
5. Read native parent/subtask and blocked/blocking relations. Also read linked
   task descriptions and declared prerequisite keys: some tasks have reciprocal
   hyperlinks because relation creation was unavailable. Do not interpret numeric
   order, list position or a Git commit alone as dependency completion.
6. For a macro ticket, show the actionable child and its prerequisites. `next`
   permits choosing the next unblocked child in the recorded dependency order;
   otherwise ask which child to implement. Stop at the selected ticket's boundary.
7. Inspect prerequisite outcomes and acceptance evidence. If a prerequisite is
   incomplete, scope is only exploratory, or a product decision gate is unresolved,
   report the blocker and ask how to proceed; do not silently implement dependencies.
   Never reopen completed work or reset manual progress to make it runnable.

## Enter the actual workflow

Discover the existing workflow rather than creating or renaming columns. The
Root GDR board currently has To-Do, Doing and Done, but IDs/names must be reread.
Move only the selected open, unblocked implementation task to the working bucket
using `harness backlog move` after reading its current placement. Confirm read-back.
No Doing bucket or an ambiguous workflow means ask; do not invent a review column.
A failed state write is not evidence that the move succeeded.

## Implement and verify

- Convert acceptance criteria into a short task list. Reproduce reported bugs and
  add failing tests before fixes when infrastructure exists.
- Work one tested layer at a time. Follow existing components, strict native-data
  boundaries, permissions, English source and Italian UI. Preserve existing data
  through explicit migrations; inspect generated migrations.
- Use the harness and independently owned environments. Do not reset databases,
  tear down another worktree or modify security controls to obtain passing tests.
- Verify the ticket's happy/error paths and actual persisted state through the API
  or integration database. UI/DOM state alone is not proof of a successful save.
- Run relevant tests/build/checks, review desktop and phone screenshots against the
  prototype, update the existing thematic manual and add its Towncrier fragment.
- Review/stage only this ticket's changes, run hooks and make the required local
  ticket commit. A macro, partial implementation, failing test or unresolved
  decision is never marked complete.

## Report the outcome and move once

Add an idempotent outcome comment with a unique stable-key/commit marker, the
commit, specification/manual paths, tests/results, screenshot/artifact references,
known limits and any remaining blockers. Distinguish local-only evidence from
remotely available evidence. Read it back before retrying an ambiguous write.

If the actual workflow has Review, move the verified ticket there for review; do
not bypass it. If it has no review gate, close into its configured Done bucket
only after the project completion requirements and local commit are verified.
Read the final task and placement back; never close the parent macro automatically.

On failure, retain an honest working/blocked state supported by the existing
workflow and add a factual blocker comment. Do not drop the ticket or claim a
successful transition. Return the confirmed task URL, commit, verification and
actual board placement. No push, deployment, deletion, release or priority change
is implied by this skill.
