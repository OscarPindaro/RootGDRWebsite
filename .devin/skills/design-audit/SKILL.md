---
name: design-audit
description: Review UI code or screenshots for consistency and accessibility, reporting findings without editing.
argument-hint: "<path, screenshot or page>"
triggers: [user]
---

# Design audit

Follow the [development workflow](../using-development-skills/SKILL.md).
State the target and report-only scope. Read the
[audit procedure](../../shared/ui/audit-discipline.md) and discover
[project conventions](../../shared/ui/project-conventions.md). Installation
does not authorize an audit or change the host project's design rules.

For code, exclude generated and vendored files. Use the styling classifications
in [visual design](../visual-design-principles/SKILL.md) and the
[code categories](references/detection-categories.md). Cite file/line locations;
claims across files need evidence from each relevant implementation.

For screenshots, use the [render categories](references/render-categories.md)
and identify the affected regions. For URLs or design-tool links, use an
authorized browser capture if available. Otherwise request a saved screenshot
and report the evidence limit. Do not infer interaction or accessibility
semantics from a single image.

Report critical, high and medium findings, their evidence and verification
limits. Group repeated causes and distinguish local corrections from changes
that affect several components. Zero findings is valid.
Do not edit or automatically invoke another skill. Suggest an additional code,
screenshot or interaction check only when it would resolve an identified gap.
