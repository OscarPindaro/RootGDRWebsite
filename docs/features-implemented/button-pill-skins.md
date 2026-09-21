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

## How it is built

- `Button.css` owns `.btn`; `Pill.css` owns `.pill`. The duplicate editorial
  rules that used to live in `main.css` (`.btn--text`, the `.pill` block and
  every `.pill--*` variant) were deleted, and the `btn`/`pill` entries were
  removed from `MIGRATION_ALLOWLIST`, so each root has one owner again.
- The phone touch target moved into `Button.css`: `@media (max-width: 700px)`
  gives `.btn { min-height: var(--touch-target) }`. The redundant
  `.docbar__actions .btn` override in `main.css` is gone.
- The editorial text action and its `html[data-accent="gradiente"]` gradient
  underline were migrated from `main.css`; the corner is no longer driven by
  Material `--button-square-*` tokens, which were deleted from `main.css`.
- `common.IconButton` composes the tooltip and the icon-only button, so the
  seven list pages use it instead of a hand-written `Tooltip` wrapper.

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
