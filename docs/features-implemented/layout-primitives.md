# Layout primitives: Grid, VStack, HStack

Pages used to lay themselves out with bare `<div>` elements carrying classes
from `main.css` (`.grid--cards`, `.stack`, `.row-inline`). Those classes are
gone: layout is a component now, so the spacing and the responsive rules live in
one place and can be changed without touching every page.

## What it does

- **`common.Grid`** — columns for lists and page splits.
  - `columns=N`: a fixed number of equal columns.
  - `min="card|cover|story|quick"`: auto-fit, as many columns as fit, none
    narrower than the matching token (`--grid-min-card`, `--grid-min-cover`,
    `--grid-min-story`, `--grid-min-quick`).
  - `split`: content beside an aside, `1.35fr / 1fr`, stacking at 1100px.
  - `gap=N`: a `--sp-*` step. `flush`: no gap (the entry-point strip, which
    shares its borders).
- **`common.VStack`** — vertical rhythm with `gap`, `align` and an `element`
  argument, so an aside stays an `<aside>` instead of becoming a `<div>`.
- **`common.HStack`** — horizontal row with `gap`, `align`, `justify`, `wrap`
  and `element` (used as `<form>` for inline forms).
- All three merge the caller's `class` and `style` instead of emitting a second
  attribute.

## How it is built

- `common/Grid.css` owns the breakpoints: `split` stacks at 1100px, `columns=3`
  drops to two at 960px, and `columns=2`, `columns=3` and auto-fit go to one
  column at 700px.
- The auto-fit minimum is a token, so the width is not repeated in the page.
- `element` exists because the previous markup used `<aside class="stack">`;
  a `<div>` would have quietly dropped the landmark.
- Values come from the `--sp-*` scale and the `--grid-min-*` tokens; nothing is
  hardcoded in the component.

## Limits

- `Grid` has no explicit column widths beyond `split`; a page needing another
  ratio adds a variant rather than an inline `grid-template-columns`.
- `HStack` only relaxes `min-width` for direct `input`/`select` children.
- The `--grid-min-*` values are the widths the old classes used; they were not
  re-derived from the prototype.
