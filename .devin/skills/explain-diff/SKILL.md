---
name: explain-diff
description: Explain a change's behavior, reasons, trade-offs and verification limits, with optional diagrams, questions and understanding notes.
argument-hint: "[scope] [--visual] [--quiz] [--record-understanding]"
triggers: [user]
---

# Explain diff

Follow the [development workflow](../using-development-skills/SKILL.md).
Accept a working tree, branch, range, patch or review scope; default to current
changes. Inspect the final diff, requirements, relevant decisions, tests and
review results. If the scope is empty or ambiguous, ask what to explain.

State what was verified and reviewed. If evidence is missing or stale, label
the change unverified and separate implementation facts from claimed behavior.
An explanation does not establish correctness or authorize repairs.

## Explain the behavior

Start with the result and why it matters. Explain the relevant flow, states,
data ownership, compatibility, failure cases, operational effects and trade-offs.
Define unfamiliar terms when needed. Include file and code references where
they help; do not turn the explanation into a list of changed symbols.
Choose examples that clarify behavior and distinguish expected outcomes from
unverified assumptions.

Default to a concise explanation in chat. With `--visual` or an explicit request,
create a diagram or visual aid only when useful, keeping generated files in a
private temporary directory. Do not start a server, install tools or fetch
assets without the required permissions.

Standalone use is repository-read-only unless understanding notes were requested.
Explain significant decisions during implementation without requiring the user
to enter a teaching session.

## Optional questions

Use `--quiz` or an explicit request to enable questions. Ask one free-response
question at a time in plain prose. Focus on predicting behavior, diagnosing a
failure or explaining a trade-off; do not test syntax, paths or memorized names.
The user may ask for an explanation, skip a question or stop at any time.
Questions never block completion or approve implementation.

If an answer differs from the explanation, check whether the gap is in the
explanation, requirements, implementation or evidence. Do not assume the user
is wrong. Explain the issue, offer another example and continue only if useful.
Do not assign scores or require a fixed number of questions or attempts.

## Optional understanding record

Use `--record-understanding` or explicit permission to retain a short note of
confirmed clarifications, unresolved concepts and deliberately skipped topics.
This is independent of quiz mode; explanation alone may clarify a decision.
Without this option, keep the discussion in chat.

Use an existing appropriate project document and confirm the destination if
unclear. Record only information useful to maintainers. Do not store raw
answers, scores, personal assessments or disputed claims as facts. Keep skipped
or unresolved topics separate from confirmed understanding. The note does not
replace requirements, implementation evidence or review results.

Close with the result, significant decisions and remaining limits. If the
discussion exposes a defect, return to the relevant planning or implementation
step within its authority; changed code needs fresh verification and review.
