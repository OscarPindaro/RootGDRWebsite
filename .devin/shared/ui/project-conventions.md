# Find project UI conventions

When an applicable UI skill is explicitly requested, inspect the project root,
agent instructions and their referenced frontend guides before using defaults.
Use bounded searches rather than reading every Markdown file.

Look for:

- `AGENTS.md`, `CLAUDE.md` and their linked design, UI and component guidance.
- `ui-guidelines/`, `docs/design/`, `docs/ui/`, `docs/style/`, and named frontend
  or design guides under `docs/`.
- `CONVENTIONS.md`, `STYLE.md` and scoped rules under `.devin/`, `.agents/`,
  `.claude/` or `.cursor/`.
- Package manifests and lockfiles identifying the framework, UI libraries,
  versions, notification tools, error reporting and icon libraries.
- Existing components, themes, tokens, localization and tests near the target.

Project rules take precedence over team fallbacks. Match existing design and
behavior; explain a conflict before proposing a change. If guidance is absent,
use only the applicable skill references. Do not create a new conventions
document or change the project's stack merely to satisfy discovery.
