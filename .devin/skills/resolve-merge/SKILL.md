---
name: resolve-merge
description: Inspect an active merge or rebase, propose conflict resolutions and verify approved changes.
argument-hint: "[conflicted paths]"
triggers: [user]
---

# Resolve merge

Follow the [development workflow](../using-development-skills/SKILL.md). Verify
an active merge or rebase through Git metadata; otherwise report that none is in
progress and stop. Inspect status and preserve unrelated staged and unstaged work.

Before writing, list conflicts and classify each as mechanical or requiring
judgment. Explain the proposed action and its evidence. Ask plainly for approval
before applying resolutions; unresolved behavior decisions need individual answers.

Mechanical cases require a checkable reason, such as byte-identical content.
Treat whitespace and line endings as potentially meaningful until verified.
For lockfiles, preserve both sides' intended manifest changes and regenerate
with the project's package manager, subject to network permissions. Do not choose
a lockfile side and discard dependency changes.

For judgment cases, compare base and both sides, explain intended behavior and
propose the combined result. Do not use a blanket choice of ours or theirs.
For a rebase, identify which revision each side represents rather than assuming
the labels correspond to the user's branches.

Respect the project's changelog generator and document identifier conventions.
Do not manually merge generated release notes or renumber stable request/ticket
identifiers without an approved repository-specific procedure.

Apply only approved changes. Never delete a file merely because it appears
duplicated; obtain explicit approval for that deletion. Stage only resolved
paths after reviewing their diffs. Leave uncertain or failed resolutions
unresolved and report them.

Check for remaining unmerged entries and tracked conflict markers, then run
relevant syntax, link, build and test checks. Review the staged result against
both sides' intended behavior. Report resolved and remaining paths, results and
limits. Do not commit, continue or abort the Git operation, rewrite history or
push without explicit authorization.
