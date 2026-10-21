---
name: staff-review
description: Review a branch, diff or named scope independently for specification compliance and code quality.
argument-hint: "[branch, diff, file or directory]"
triggers: [user]
---

# Staff review

Follow the [development workflow](../using-development-skills/SKILL.md).
Review only; a review request does not authorize fixes.

Resolve scope before starting. For uncommitted work, include staged, unstaged
and relevant untracked files. Compare a named branch with its intended base,
confirming the base when ambiguous. With no scope, use current changes; if
there are none, ask what to review. Preserve unrelated work.

## Arrange independent review

Use a separate context without the implementation conversation. Follow project
delegation permissions: confirm the reviewer, scope and access unless an existing
explicit approval already covers them. Do not assume a general implementation
request authorizes an agent. If independence is unavailable, report that limit
and ask whether a same-context review would still be useful.

Provide the diff or scoped files, user requirements, relevant specifications,
project instructions and verification evidence. Exclude the implementer's
conclusions and other review verdicts. Use a read-only tool set; do not give the
reviewer unrestricted shell, external services or credentials. Tests that write
to an isolated environment need separate verification authorization.

Give the reviewer the [review procedure](references/review-procedure.md).
It reads the changed code first, then requirements and standards, and returns
separate specification and quality assessments. Wait for the result.

## Report and follow up

Present findings first, ordered by severity with file/line references, followed
by assumptions and verification limits. Preserve the reviewer's evidence,
severity and uncertainty when summarizing. No findings is a valid result; it
does not prove untested behavior.

For re-review, supply prior findings, the fix diff and fresh verification.
Check whether each finding is addressed and whether the fixes introduce defects;
do not reopen unchanged areas without new evidence. Repairs follow the existing
implementation authority. New scope or conflicts with approved decisions return
to the user.
