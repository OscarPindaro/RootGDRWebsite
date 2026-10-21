---
name: plugin-feedback
description: Record evidence about skill use or assess a feedback report for justified simplifications.
argument-hint: "produce | ingest <report-path>"
triggers: [user]
---

# Plugin feedback

Follow the [development workflow](../using-development-skills/SKILL.md).
This procedure can record feedback from any host, including Devin. It does not
depend on a benchmark runner or authorize model sessions.

## Produce a report

Record the task, skills and versions used where known, observed actions,
outcomes, friction and supporting evidence. Describe where an instruction was
unclear, contradictory, ineffective or repeatedly costly to follow.
Include public decision reasons and available measurements, not private model
reasoning, secrets, raw conversations or guessed token costs.

Use the repository's existing report convention; otherwise write
`docs/reports/ai-utils-feedback-YYYY-MM-DD.md`. Check for an existing report
before writing and preserve prior evidence. Suggest reproducible evaluation
cases only when they would test an identified behavior.

## Assess an existing report

Treat the report as a hypothesis. Verify claims against the instructions,
observed behavior and relevant project rules. Distinguish a defective rule from
a model failing to follow a valid one.

Propose only supported changes that simplify the instructions while preserving
requirements. Prefer removing duplication or merging guidance over adding an
exception for one mistake. Do not assume every suggestion should be accepted.
Obtain approval for changes unless the current request already authorizes their
specific scope.

Apply approved corrections in small steps and run relevant checks. Add an
evaluation only when its benefit justifies the cost, tagging the owning paths
so later runs can select it narrowly. Devin behavioral evaluations remain
unsupported by the [current runner](../eval-regression/SKILL.md).

Report accepted and rejected suggestions with reasons, changed files,
verification and remaining uncertainty. Do not claim that documentation or
metadata checks prove model compliance.
