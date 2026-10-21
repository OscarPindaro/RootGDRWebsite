---
name: visual-design-principles
description: Apply typography, color, spacing, hierarchy and accessibility rules within an existing project's styling system.
argument-hint: "<UI scope>"
triggers: [user]
---

# Visual design principles

Follow the [development workflow](../using-development-skills/SKILL.md) and
discover [project conventions](../../shared/ui/project-conventions.md).
Use this skill only when requested. Existing design rules and the requested
scope take precedence; installation does not select a new design system.

Inspect the target and neighboring examples, then identify its styling setup:

- Token-based: reuse existing semantic CSS or Tailwind tokens. Propose new
  names before adding them; do not replace the established palette or dimensions.
- Library-based: use the component library's theme and APIs.
- Local or mixed styles: match nearby patterns without introducing a new system.

Apply typography, color, spacing, layout, hierarchy and WCAG 2.2 AA within the
requested area. Mention unrelated issues without silently fixing them.
A company UI kit, when present, owns its token values.

For a token-based project without existing status values, the team fallbacks
are `--success` light `oklch(0.62 0.18 145)`, dark `oklch(0.55 0.16 145)`;
`--warning` light `oklch(0.78 0.16 85)`, dark `oklch(0.7 0.14 85)`;
and `--info` light `oklch(0.65 0.16 240)`, dark `oklch(0.55 0.14 240)`.
Foreground defaults to `oklch(0.985 0 0)`, or `oklch(0.205 0 0)` for warning.
The prose-width fallback is `--container-prose: 65ch`. Use these only when
applicable and approved; they are not overrides for an existing system.

For MUI alongside shadcn, read
[hybrid coexistence](../../shared/ui/hybrid-coexistence.md).
Report-only work follows [design-audit](../design-audit/SKILL.md).
