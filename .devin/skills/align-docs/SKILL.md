---
name: align-docs
description: Check stale claims, conflicting guidance and documentation structure, then apply authorized corrections using the repository's conventions.
argument-hint: "[scope] [--check | --clean]"
triggers: [user]
---

# Align docs

Follow the [development workflow](../using-development-skills/SKILL.md).
Maintain the repository's existing documentation conventions. Chronicles are
optional; use existing specifications, feature manuals, decision records and
indexes where they serve the same purpose. Do not introduce a mandatory atlas,
frontmatter format, folder layout or duplicate tracker status.

## Establish scope

Inspect the checkout, agent instructions, human entry point and relevant indexes.
With active task context, include documentation the task changed or invalidated.
Otherwise inspect the entry points and their references, or the named scope.
Exclude dependencies, caches, generated output and vendored documents.

`--check` reports without writing. A normal run reports issues before making
unambiguous corrections within its scope; uncertain claims remain unchanged.
`--clean` inspects all first-party documentation and requires approval of an
exact change proposal before any edits. Do not apply a repository-wide cleanup
as a side effect of routine maintenance.

## Verify claims

Identify missing, stale, contradictory, duplicated and hard-to-find information.
For each issue, cite the document and evidence that supports the correction.

- Check implemented behavior against code, tests and configuration.
- Check procedures against current commands, tooling and CI.
- Treat approved requirements as intended behavior; missing implementation does
  not authorize weakening the requirement.
- Preserve historical decisions and their reasons. Distinguish dated evidence
  from claims about current behavior.
- Check runtime claims against authorized observations. Without access, report
  the uncertainty rather than asserting that a deployment or service is current.

Do not guess which source wins when authorities disagree. Explain the conflict
and ask for the decision needed. Capture durable session facts only when absent
from their existing home; omit raw conversations and transient progress.

## Keep instructions focused

Keep `AGENTS.md` short: essential rules, project orientation and links to scoped
guidance. Move detailed procedures to their appropriate existing documents when
that restructuring is approved. Do not append incident histories, temporary
plans or routine outcomes to the always-read instructions.

Preserve every required rule when shortening the entry point. Prefer one
authoritative location and links over repeated guidance. Use existing indexes
to make documents discoverable. Keep machine-specific facts in the repository's
established private location; do not create provider-specific configuration.

## Apply and verify

For structural changes, propose the source, destination, surviving information
and link updates, then ask in plain prose before moving, merging or archiving.
Deletion requires explicit approval for the named files. Preserve unique facts,
decisions and useful history; leave uncertain documents active.

For a large approved cleanup, verify a small representative batch before
continuing. Preserve stable identifiers and project-specific metadata. Never
rewrite historical decisions to make them appear current.

Check links, indexes, referenced paths, metadata and affected commands. Report
what was corrected, supporting evidence and remaining gaps. Follow the project's
commit rules; do not change application behavior or external tracking state.
