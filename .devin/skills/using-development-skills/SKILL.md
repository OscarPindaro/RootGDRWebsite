---
name: using-development-skills
description: Clarify, plan, implement and verify development work, using existing specifications when they are sufficient.
argument-hint: "<request, specification or implementation scope>"
triggers: [user]
---

# Development workflow

Read project instructions and relevant specifications first. Inspect the checkout
and preserve unrelated work. Resume existing work at its recorded step.

Speak and write like a library maintainer: concise, calm, precise and practical.
Explain behavior, compatibility, evidence and uncertainty. Ask questions in plain
prose, one decision at a time, with a recommendation and its trade-off.

## Establish scope and authority

Follow repository instructions for tracking, documentation, commits and delivery.
Keep tracking-system operations in the repository's own tools and skills. Do not
introduce a board, duplicate live status in documents or require a new layout.
Recording an idea does not authorize implementation.

Picking up a sufficiently specified implementation ticket authorizes its scope.
Proceed when scope, expected behavior, acceptance criteria and approach are
clear enough, with no consequential decision unresolved. Size alone does not
require another plan approval. Write a short execution checklist when useful;
do not reopen decisions already settled in the ticket or linked specification.

For other requests, proceed directly when the result, solution and verification
are clear, the change is reversible, and no product or design decision remains.
Otherwise inspect first, resolve material questions, and obtain approval for the
resulting plan before implementation. An idea-only ticket follows this path.
Reviews and audits deliver findings; they do not authorize fixes.

## Clarify and plan when needed

Use the [brainstorming playbook](../brainstorming/SKILL.md) for unresolved
decisions and [research guidance](../best-practices/SKILL.md) when external
evidence could change the choice. Discover facts before asking the user.

Settle the outcome, scope, exclusions, approach, affected areas, verification and
risks. If a prescribed approach conflicts with verified constraints, explain the
problem and recommend an alternative before editing. Do not silently substitute
your preferred design. Ask plainly for approval of the plan.

Use the project's existing specification and decision records. Preserve durable
decisions and enough execution state to resume; avoid duplicate documents.
Approval covers the stated work and checks, not new scope or destructive actions.

## Implement and verify

Work in small slices, following established code and data boundaries. Run the
nearest useful check after each slice. Use the [testing playbook](../create-test/SKILL.md)
to establish observable outcomes and regression checks.

Run fresh checks and compare the final diff with the specification in both
directions: required behavior is present and unrequested behavior is absent.
Report pre-existing failures. Do not weaken or skip checks to claim success.
Execute runnable documentation examples against their actual dependencies.

For substantial work, propose independent verification and review. Obtain
explicit approval for the agents, scope and environment before launching them;
an implementation request or general plan approval alone does not authorize
delegation. Use clean contexts and provide requirements, scope and evidence
without the implementer's conclusions. A verifier runs behavior; a reviewer
checks specification compliance and quality. Report when either was not done.
Use the [staff-review playbook](../staff-review/SKILL.md) when arranging the
review. A [cross-model review](../phone-a-friend/SKILL.md) is an optional escalation
with its own approved provider, model, access and cost limits.

## Finish

Fix in-scope findings and rerun affected checks. Ask when findings require new
authority or contradict an approved decision. Reconsider an approach after
repeated unsuccessful fixes.

Update affected documentation in its existing home using the
[maintenance playbook](../align-docs/SKILL.md). Chronicles are optional; follow
the repository's existing way of recording decisions. Keep agent instructions
short and focused rather than appending task history.

Explain significant decisions, verified results and remaining limits using the
[explanation playbook](../explain-diff/SKILL.md) where useful. Quizzes and
understanding records are optional and never block completion.
Follow project-specific commit requirements; otherwise commit only when
requested. Never infer permission to push, deploy, publish a release or change
external state.
