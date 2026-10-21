# Button and Pill skins

One action-button skin and one status-pill skin, both part of the printed-atlas
identity.

## What it does

- `common.Button` is the only action-button markup. It is a low-radius control
  (`--radius`) with a visible ink rule (`--rule-ink`) and a flat fill, replacing
  the transparent border and the accidental `--radius-full` oval. The `text`
  variant is the editorial mono, uppercase link with a one-pixel underline and
  no box border.
- `shape` still emits the `btn-{shape}` class for callers and `ButtonGroup`, but
  every button now shares the same low radius, so the corner no longer changes
  with it.
- `common.Pill` is the only status pill. It keeps the prototype's capsule
  (`--radius-full`) with an ink rule, a surface fill and mono, uppercase type,
  and carries both the M3 status/role names and the product variants (`master`,
  `player`, `vermilion`, `cobalt`, `ochre`, `forest`, `plain`, `npc`, `draft`,
  `act1`, `act2`, `act3`).
- A state pill stays quieter than a command: the pill fills with the surface or
  a status tint, the primary command fills with the accent.
- The status and role labels are 12px mono text, so every foreground pair needs
  4.5:1. `neutral`, `success`, `warning`, `accent`, `role-admin` and
  `role-member` keep their tinted fills and derive a darker ink from their own
  semantic colour. `danger`, `info` and `role-dev` already pass and keep their
  token unchanged.
- `common.Avatar` keeps its eight categorical fills. Its initials are bold but
  small (11–13px), so bold is not a large-text exception: the orange entry takes
  the atlas ink and the pink entry takes a private near-black.

## How it is built

- `Button.css` owns `.btn`; `Pill.css` owns `.pill`. The duplicate editorial
  rules that used to live in `main.css` (`.btn--text`, the `.pill` block and
  every `.pill--*` variant) were deleted, and the `btn`/`pill` entries were
  removed from `MIGRATION_ALLOWLIST`, so each root has one owner again.
- The phone touch target moved into `Button.css`: `@media (max-width: 700px)`
  gives `.btn { min-height: var(--touch-target) }`. The redundant per-bar
  override in `main.css` is gone; Docbar's own `Docbar.css` only sizes the
  command row on a phone (`.docbar__commands .btn { flex: 1 1 auto }`).
- The editorial text action and its `html[data-accent="gradiente"]` gradient
  underline were migrated from `main.css`; the corner is no longer driven by
  Material `--button-square-*` tokens, which were deleted from `main.css`.
- `common.IconButton` composes the tooltip and the icon-only button, so the
  seven list pages use it instead of a hand-written `Tooltip` wrapper.
- Each repaired pill mixes 70% of its own semantic colour with `--ink`:
  `color-mix` keeps the hue recognisable and leaves the role tokens independent,
  so a later change to one role does not move another role's foreground.
- The avatar foregrounds live on the existing `.cat-*` rules. Orange gets
  `--ink` (5.88:1); pink gets pure black (4.67:1) because no atlas ink reaches
  4.5:1 on that fill — `--ink` is 4.06:1 and `--surface` is 4.42:1. The rule
  carries a line-scoped `design-tokens: off` marker for that one literal.

## Used by

- `editorial.Docbar`, `editorial.Cover`, `editorial.ImageEditor`.
- The world, character, NPC, place, session, story and page list and detail
  pages.
- `pages/worlds/WorldOverview` and `WorldSettings`.

## Limits

- `ButtonGroup` keeps its own connected/standard group corners; only the
  standalone `common.Button` lost the `shape`-driven radius.
- The pill is a status mark, not a control; an interactive filter is a
  `ButtonGroup` or a `Button`.
- The repaired status/role inks are darker than the raw status hues. That is
  the contrast repair; the fills and the role tokens are unchanged.
- The pink avatar is the only entry whose initials are not the surface colour.
  Every other atlas ink is below 4.5:1 on that fill, so it keeps the fill and
  takes black initials.
