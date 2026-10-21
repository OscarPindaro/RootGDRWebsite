---
name: brainstorming
description: Resolve purpose, scope, data boundaries and consequential design decisions before implementation planning.
argument-hint: "<idea or unresolved design>"
triggers: [user]
---

# Brainstorming

Follow the [development workflow](../using-development-skills/SKILL.md). If no
topic is supplied or clear from the conversation, ask what to explore and stop.
Inspect existing specifications and implementation before asking about facts.

The user decides the desired outcome and business trade-offs. Recommend the
technical approach with evidence. Preserve established preferences and decisions.
Ask one material question at a time in plain prose, explaining your recommended
answer and its cost. Do not repeat questions the existing specification answers.

Work through:

- Who needs the change, what problem it solves and what success looks like.
- Included behavior, exclusions and compatibility requirements.
- Data ownership, relationships and boundaries, using concrete awkward cases.
- Failure paths, permissions, concurrency and assumptions that could invalidate
  the approach.
- Meaningfully different alternatives and the simplest suitable choice.
- Observable acceptance criteria and how they will be checked.

Use [research guidance](../best-practices/SKILL.md) only where current evidence
could change the decision. Mark unresolved questions explicitly. A request for
fewer questions means group essential decisions with recommendations; it does
not authorize guessing about consequential choices.

Return the settled decisions and remaining uncertainty. Do not implement during
brainstorming or present unresolved choices as an approved specification.
When implementation is requested, prepare the plan and seek approval through the
development workflow. An intake request may remain an incomplete recorded idea.
