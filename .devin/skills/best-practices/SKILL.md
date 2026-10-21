---
name: best-practices
description: Research a technical decision and recommend an approach supported by current evidence and project constraints.
argument-hint: "<topic or decision>"
triggers: [user]
---

# Best practices

Follow the [development workflow](../using-development-skills/SKILL.md) for
communication, authority and project conventions. Research does not authorize
implementation or dependency upgrades.

Identify the decision, existing hypotheses, constraints and established user
preferences. Inspect repository-specific claims locally. Ask only when missing
context could materially change the recommendation.

Match research depth to the decision: a narrow fact may need one lookup; costly,
risky, disputed or fast-changing choices need stronger evidence. Prefer official
documentation, specifications, source and reproducible measurements. Respect
network permissions; report when current sources cannot be checked.

For claims about a dependency, identify the installed version and check its
documentation. Compare current guidance where relevant, separating compatibility
with the installed version from reasons to consider an upgrade. Test executable
claims when practical; an import succeeding does not prove behavior.

Cite material claims. Separate observed facts from inference and explain
disagreement, uncertainty and where the recommendation applies. Recommend for
this project's goals rather than generic popularity. If evidence conflicts with
a project preference, explain the consequence and propose a change explicitly.

Return a concise recommendation, relevant alternatives, supporting sources and
unresolved limits. Save research only when it will remain useful after the task,
using the project's existing documentation structure.
