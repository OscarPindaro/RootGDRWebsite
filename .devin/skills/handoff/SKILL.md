---
name: handoff
description: Write a self-contained temporary note so another conversation can resume the work safely.
argument-hint: "[focus or next action]"
triggers: [user]
---

# Handoff

Follow the [development workflow](../using-development-skills/SKILL.md).
Capture enough context to continue without the original conversation. Preserve
the user's request, settled decisions, useful discoveries, current state and
next action. Do not copy the conversation or raw logs.

## Destination

Use the operating system's temporary directory by default, respecting `TMPDIR`
where applicable. Create a private directory and a new timestamped file such as
`handoff-YYYY-MM-DD-HHMMSS-topic.md`. Verify the parent location and avoid
overwriting another note. Write the absolute path in the handoff.

A requested durable or cross-machine destination overrides the temporary default.
Temporary files are local and may disappear; report that limit. Do not copy
secrets, environment contents, credentials or unrelated private information.

## Content

Keep these sections:

- What the user wants: the intended result, reason and scope.
- Where things stand: completed, incomplete and blocked work, with verification
  results and unverified claims distinguished.
- Next step: the requested continuation or the next supported action.

Include other sections only when useful:

- Decisions that must survive, with reasons and relevant rejected alternatives.
- Project rules, dependencies and known environment problems.
- Files and existing work: repository/worktree path, branch, relevant commits,
  staged, unstaged and untracked changes, including work owned by someone else.
- Environments and resources: ownership, live services and restrictions on resets
  or teardown.
- Permissions already granted, their scope and decisions still requiring approval.
- Existing specifications, plans, manuals, decision records, task references and
  skills needed to continue.
- Open questions and who can resolve them.

Use exact wording when a decision must not be reinterpreted. Verify current
checkout and file facts with read-only inspection where practical. Label
historical observations instead of presenting them as fresh verification.
Do not start services, clean environments, change task status or commit while
preparing the note. A handoff does not grant new authority to the next agent.

## Deliver

Return the absolute file path and the instruction to read it and continue from
the Next step section. Do not duplicate the entire note in chat or add transient
handoff details to permanent agent instructions.
