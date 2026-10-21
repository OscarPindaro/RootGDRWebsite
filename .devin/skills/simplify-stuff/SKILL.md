---
name: simplify-stuff
description: Simplify an agreed set of documents or instructions while preserving requirements, technical details and references.
argument-hint: "<files, directory or instruction set>"
triggers: [user]
---

# Simplify stuff

Follow the [development workflow](../using-development-skills/SKILL.md).
Resolve the requested scope; if none is supplied or clear, ask what to simplify.
This is a writing and instruction cleanup. Application behavior changes belong
in the [refactoring workflow](../refactor/SKILL.md).

Read every file in scope, relevant references and incoming links before editing.
Identify each document's purpose and the facts repeated across documents.
Use the repository's existing structure and writing rules.

Write concise, calm, practical prose. State the result or rule directly,
explain unfamiliar terms when needed and remove filler, repetition and
unnecessary labels. Preserve the detail another maintainer needs to act safely.
Do not impose a formal controlled-language standard or an arbitrary length limit.

Give repeated guidance one appropriate home and link to it from other files.
Preserve exact names, commands, paths, constraints, exceptions, examples carrying
requirements, decisions and verification details. Do not remove a rule merely
because it seems obvious or concerns a rare but documented failure.

Make authorized wording changes within scope. Before moving or merging files,
propose the resulting structure and link changes and obtain approval. Deleting
files needs explicit approval for those files. Relocate useful information
rather than losing it to make the text shorter.

Review the diff for changed meaning and accidental omissions. Confirm important
names and requirements remain, links and section references resolve, and runnable
examples still work when changed. Do not claim verification that was not run.
Report significant removals and their reasons; preserve them in the existing
decision record when useful. No new chronicle is required.
