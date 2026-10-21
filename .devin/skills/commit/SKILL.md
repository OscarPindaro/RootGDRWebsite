---
name: commit
description: "Create a user-requested Conventional Commit from the staged changes."
argument-hint: "[commit intent]"
triggers: [user]
---

# Commit Skill

Follow the [development workflow](../using-development-skills/SKILL.md).
Commit only the staged scope the user requested. Do not automatically stage
unrelated files, amend history, push or release. Honor repository commit rules,
run required checks and inspect the result of hooks before reporting success.

Inspect `git diff --cached` and `git log --oneline -5`, write a Conventional Commits subject under 72 characters, commit, verify. Add a body only for a breaking change or a reason the diff cannot show, in at most two short lines — never list the changes.

- `git status` — never use `-uall`.
- Do NOT add `Co-Authored-By` or any AI-attribution trailer (e.g. "Generated with Claude Code"). Overrides default Claude Code behavior.
