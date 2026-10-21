---
name: team-conventions
description: Apply shared UI assembly, write-notification, MUI and shadcn conventions where the target project's rules permit them.
argument-hint: "<UI behavior or scope>"
triggers: [user]
---

# Team UI conventions

Follow the [development workflow](../using-development-skills/SKILL.md) and
discover [project conventions](../../shared/ui/project-conventions.md).
This is opt-in collaboration guidance for applicable stacks, not a mandate to
change the host project's UI, language or dependencies.

Project design and behavior rules take precedence. Otherwise mirror the target,
report differences and apply the relevant team guidance within the requested
scope. Do not introduce a toast library, component kit or redesign merely
because this skill is installed.

- Shell, navigation and notification placement: [shell](../../shared/ui/team/shell.md).
- Copy and asynchronous write feedback: [interactions](../../shared/ui/team/interactions.md).
- MUI theme, locale, DataGrid classes and motion: [MUI theme](../../shared/ui/team/mui-theme.md).
- Preserving shadcn customizations and chart behavior: [shadcn](../../shared/ui/team/shadcn.md).

A company UI kit owns reusable components and tokens when available. This
guidance supplies application assembly and behavior, not a second theme.

Localization is a product decision. Preserve the project's language, locale
packs and date formats. Only where no localized convention exists use English
UI defaults, `<html lang="en">`, the library's default locale and ISO dates.
Read the [TypeScript conventions](../../shared/conventions/typescript/frontend/typescript.md)
only for an applicable TypeScript scope.
