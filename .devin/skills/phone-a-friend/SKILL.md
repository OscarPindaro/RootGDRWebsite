---
name: phone-a-friend
description: Obtain an independent second-model review of a plan or change, then resolve findings through one evidence-based response round.
argument-hint: "[plan or review scope] [preferred model or provider]"
triggers: [user]
---

# Phone a friend

Follow the [development workflow](../using-development-skills/SKILL.md).
Review a supplied plan or implementation scope. Resolve ambiguity before
starting. If `PHONE_A_FRIEND=1`, stop: the partner must not launch another review.

## Agree on the run

Identify the host model and an available partner from another model family.
Confirm the provider, model, effort where supported, scope, read access, timeout
and cost limits before starting unless the user already approved this run.
Do not silently select a premium model, high effort or extra reviewers. If prices
are unknown, say so; do not invent a cost estimate.

Use the [provider guidance](references/providers.md) for Devin, Claude Code and
Codex. A same-family review may be useful but is not a cross-family second
opinion. Report missing capabilities rather than silently substituting a model.

## Prepare a neutral review

Keep packets, verdicts and logs in a private temporary directory outside the
reviewed repository. Provide the user's requirements, artifact, applicable
standards and relevant file paths. Remove secrets and unrelated private data.
Do not include the author's reasoning, verdict or another reviewer's report.
Limit each reviewer to its own packet and output so sibling verdicts stay hidden.

Require the [review procedure](../staff-review/references/review-procedure.md).
Each finding also states what evidence would change it, its estimated likelihood
and confidence separately. Missing context must be reported, not guessed.
For a disputed plan section, request a proposed correction and its reason.

The partner reviews read-only. Do not grant production access, database writes,
state-changing endpoints or unrestricted commands. A prose instruction is not
a substitute for tool restrictions. If adequate restrictions cannot be applied,
stop and explain what is missing.

For implementation reviews, also arrange a separate local review using the
[staff-review procedure](../staff-review/SKILL.md), with explicit authorization.
Reuse an independent verdict only when it covers the same diff and scope.
Keep the reviews separate until both finish. If the second review is not
authorized or available, report that the result has only one reviewer.

## Respond once and close

Answer each finding once: accept it, counter it with new evidence, or mark it
uncertain. Resume only this partner's session with the original access limits;
if safe resume is unavailable, report that limit. The partner marks each point
confirmed, withdrawn or uncertain. A changed verdict without new evidence does
not establish agreement. Do not start a third discussion round.

Group findings by location and claim, identifying agreement and findings unique
to either review. Preserve withdrawn findings and unresolved disagreement.
Assess severity using evidence and impact, not the model's label alone.

Return material unresolved issues and product decisions to the user, showing
both positions and their evidence. Model agreement does not authorize migrations,
authentication changes, deletion or other hard-to-reverse actions. Fixes require
the normal implementation authority.

Report models used, results, limits, elapsed time and usage/cost when available.
With permission, preserve the report in the project's existing decision record.
Do not create a new documentation convention or retain sensitive transcripts.
