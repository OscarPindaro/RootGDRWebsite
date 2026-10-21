---
name: mui
description: Work on existing MUI 6+ components, themes, fields and DataGrid, including projects that also use shadcn.
argument-hint: "<MUI component or scope>"
triggers: [user]
---

# MUI

Follow the [development workflow](../using-development-skills/SKILL.md).
This skill applies only to an explicitly requested MUI scope. It does not
install MUI, convert a frontend or replace project design rules.

## Check applicability

Require an MUI dependency or `@mui/*` import and an identifiable
`@mui/material` major version of at least 6. Otherwise report the detected
setup and stop. Do not upgrade the library to make the skill applicable.

Check for shadcn signals such as `components.json`, a UI component directory
and shadcn tokens. Identify whether the project uses MUI alone or both libraries.
Discover [project conventions](../../shared/ui/project-conventions.md).
Use the project's design-system allocation rules when present; otherwise read
[hybrid coexistence](../../shared/ui/hybrid-coexistence.md).

## Implement within the existing system

Read [MUI patterns](references/mui-patterns.md). The team target uses
`cssVariables: true`; report an existing configuration difference before changing
it. MUI components use `theme.palette`, `theme.spacing()` and breakpoints, not
shadcn variables or raw replacements.

Preserve portal, focus and layer behavior. Do not mix MUI and shadcn text inputs
in one form or swap libraries for an established role without an approved
project decision.

`ButtonGroup` provides visual grouping. Selection uses `ToggleButtonGroup`
with `value`, `onChange` and `exclusive` where appropriate.
For report-only work, use the [audit categories](../design-audit/references/detection-categories.md).
