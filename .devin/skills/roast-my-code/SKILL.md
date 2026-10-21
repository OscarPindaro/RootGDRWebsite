---
name: roast-my-code
description: Present an evidence-based code review with humor aimed at the code, only when explicitly requested.
argument-hint: "[--fix] [review scope]"
triggers: [user]
---

# Roast my code

Use the [staff-review procedure](../staff-review/SKILL.md), including its scope
and delegation permissions. Obtain the review before changing its presentation.
Do not launch additional reviewers simply to produce jokes.

Only an explicit request for a roast enables the sarcastic tone. Apply it to
code and design choices, never the author. Keep findings, severity, evidence,
uncertainty and corrections intact. Do not invent issues or exaggerate their
impact for humor. Stop the tone if the user asks; ordinary replies retain the
project's communication style.

Without `--fix`, report and stop. With `--fix`, present the critical and high
findings and ask in plain prose which to address. The flag alone does not select
fixes or authorize new scope. Implement the approved selection through the
[development workflow](../using-development-skills/SKILL.md), then rerun checks.
Leave other findings in the report without silently fixing them.
