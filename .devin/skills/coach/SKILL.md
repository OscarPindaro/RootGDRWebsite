---
name: coach
description: Suggest evidence-based improvements from the user's native conversation history, including Devin, without capture hooks or an analytics database.
argument-hint: "[period or project]"
triggers: [user]
---

# Coach

Follow the [development workflow](../using-development-skills/SKILL.md) and
[native-history procedure](../retro/references/native-history.md). Read the
history directly; do not install DuckDB, ingest sessions or enable reminders.
Use the current project and last seven days unless the user chooses another scope.

## Review prior advice

With an existing authorized coaching report, read its pending and declined
suggestions. Follow up when the selected history provides new evidence.
Do not repeat declined advice or reinterpret an accepted trade-off as a mistake.
If no report is available, proceed without claiming a follow-up.

Read the user's interactive sessions, excluding automated runs and subagent work
when native metadata identifies them. If session origin is uncertain, say so
instead of attributing autonomous activity to the user.

## Find useful improvements

Inspect bounded exchanges that show repeated corrections, unclear requests,
avoidable rework, setup problems or practices that helped. Check the surrounding
conversation before assigning a cause. A permission requirement is not a defect
merely because it produces prompts.

Return up to three supported suggestions and an example of what worked when
the evidence supports one. Do not fill a quota. Sparse history warrants a short
report or no advice.

For each suggestion, give the observed exchange and its source identifier,
why the change would help, and the smallest useful next step. A proposed file
change names the file and text, but is not applied automatically. Keep unrelated
projects, secrets and transcript quotes out of proposed repository instructions.

Describe behavior without judging the person. No personality assessments,
grading, cost commentary or general advice unsupported by the selected history.

## Deliver and retain only with permission

Present the advice in the user's language. Offer proposed changes in plain
prose and apply them only after approval through the normal workflow.
The user may decline or stop without further justification.

Ask before saving a persistent coaching report unless this invocation already
requests one. Use an agreed private location outside the repository by default.
Retain dated suggestions, their evidence references, follow-up and applied,
pending or declined decisions. Preserve prior choices when updating a report.
Without permission to save, keep the result in chat and state that follow-up
across sessions cannot rely on a saved report.

Do not commit, modify history storage or start a recurring analysis.
