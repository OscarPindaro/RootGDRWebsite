# Component vocabulary

The finite set of public options an author may pass to `common.Button`,
`common.Pill` and `common.Grid`, and the rule for extending it. The project
owner delegated the choice to the coordinator on 2026-10-23; this record is the
accepted outcome for REQ-0019/T18 and the input for T19, T20 and T31.

## What it does

### Public options

| Component | Argument | Supported | Experimental | Reserved no-op |
|---|---|---|---|---|
| `common.Button` | `variant` | `primary`, `secondary`, `text`, `danger` | — | — |
| `common.Button` | `size` | `xs`, `sm`, `md` | `lg`, `xl` | — |
| `common.Button` | `shape` | — | — | `round` (default), `square` |
| `common.Pill` | `variant` | `neutral`, `success`, `danger`, `warning`, `info`, `accent`, `role-admin`, `role-dev`, `role-member`, `master`, `player`, `draft`, `plain`, `forest`, `npc`, `vermilion`, `cobalt`, `ochre`, `act1`, `act2`, `act3` | — | — |
| `common.Grid` | `columns` | `2`, `3` | — | — |
| `common.Grid` | `gap` | `1`, `2`, `3`, `4`, `5`, `6`, `8`, `10`, `12`, `16`, `20` | — | — |
| `common.Grid` | `min` | `card`, `cover`, `story`, `quick` | — | — |
| `common.Grid` | flags | `flush`, `split`, `document` | — | — |

`lg` and `xl` keep their CSS and their design-kit specimens. They are excluded
from the supported product list and are not used by a production caller; T20
does not delete them. `shape` on a standalone button emits `btn-round` or
`btn-square`, which no stylesheet styles. It is kept because `Topbar`,
`MenuTrigger`, `IconButton`, `ButtonGroup` and the design kit pass it; removing
it would ripple without a visible change.

### Decision ownership

| Decision | Owner | Consequence |
|---|---|---|
| The supported, experimental and reserved options above | Project owner; delegated to the coordinator on 2026-10-23 | Authors use this list; T19 enforces it |
| Rejecting an unsupported value | T19 | Runtime rejection; this ticket adds none |
| Removing unused or experimental surface | T20, only from this record | A retained option stays even when no caller uses it |
| Token checks and private geometry | T31, following "Private geometry" below | A local rem/clamp value is not a token violation |
| Stored tint ids and live aliases | Project owner | `--p1`–`--p12`, `tint="p8"`, `tint="ochre"` and the alias names are not renamed for consistency |
| Adding a public option | Project owner | The extension rule below applies |

### Machine-checked list

`tests/frontend/test_component_vocabulary.py` reads this block and compares it
with the component templates, their stylesheets, the spacing and grid tokens in
`main.css`, and the design-kit callers.

<!-- component-vocabulary:start -->
```text
button.variant: primary secondary text danger
button.size: xs sm md
button.size.experimental: lg xl
button.shape.reserved-noop: round square
pill.variant: neutral success danger warning info accent role-admin role-dev role-member master player draft plain forest npc vermilion cobalt ochre act1 act2 act3
grid.columns: 2 3
grid.gap: 1 2 3 4 5 6 8 10 12 16 20
grid.min: card cover story quick
grid.flags: flush split document
```
<!-- component-vocabulary:end -->

### Invalid values today

No template validates a finite choice yet. An unknown value is interpolated into
a class and renders without the matching rule:

- An unknown `Button.variant` keeps the base `.btn` geometry and has no variant
  fill. An unknown `Button.size` keeps the `md` defaults because `.btn` sets
  `--button-height-md`, `--button-padding-md` and `--button-icon-md`.
- An unknown `Pill.variant` keeps the base `.pill` surface fill.
- An unknown `Grid.columns` emits `grid-columns-N` with no rule, so the grid has
  one implicit column.
- A `Grid.gap` that is not a spacing step sets `--grid-gap: var(--sp-N)` to an
  undefined token. The `gap` declaration is invalid at computed-value time and
  the grid loses its gap; the `var(--sp-6)` fallback in `Grid.css` does not
  apply because `--grid-gap` is defined.
- An unknown `Grid.min` leaves `--grid-min-*` undefined, so
  `grid-template-columns` is invalid and the grid has one implicit column.

T19 replaces this behavior with a clear rejection that names the component,
argument and value.

### Private geometry

A component's own geometry stays in its stylesheet: its rem and clamp values,
BEM internals, and one-off alignments. Examples are the pill's `0.35rem` gap and
`0.15rem` vertical padding, and the text button's `0.06em` letter spacing. These
are not public options and do not need a token in `main.css`. A value that is
shared across components, or that belongs to the palette or a shared scale,
still belongs in `main.css`.

The `design-tokens` hook (`E920`) enforces that boundary:

- A colour literal is a palette violation. The palette lives in `main.css`.
- A `px` length is an absolute size outside the approved local form. A shared
  step or measure uses a token; private geometry uses a local `rem`/`clamp`
  value. Border, outline and shadow declarations may stay in `px` because they
  describe a line or its offset, not a spacing choice.
- `rem`, `em` and `clamp` values pass as private geometry. Rewriting a shared
  `px` value as `rem` does not move it into the token layer: passing the hook
  is not proof of token compliance, and review still asks whether the value is
  shared.

### Retained opt-outs

`/* design-tokens: off */` on a line, or in the first three lines of a file,
skips that line or file. Each current use has a reason the policy cannot
express:

- `common/Avatar.css` `.cat-5 { color: #000; }` — no atlas ink reaches 4.5:1
  on the pink categorical fill (`--ink` is 4.06:1, black is 4.67:1).
- `layout/Rail.css` `text-underline-offset: 3px` — a one-off underline
  alignment, not a shared measure.
- `layout/Page.css` `left: -9999px` — the off-screen-until-focused technique,
  not a size choice.
- `pages/showcase/Showcase.css` — the file opt-out for the style guide's fixed
  demo boxes. A file opt-out is for a design-kit stylesheet, not product CSS.

The hook also skips values inside `url(...)` (inline SVG is image data, not
theme CSS), `@media` queries (breakpoints are not spacing), and comments
(prose about a value is not the value).

### Extension rule

Add a public option only when a reusable component needs it. The change includes
the stylesheet rule or token, a design-kit specimen, a test assertion, and an
entry in the machine-checked list above. A one-off layout or measurement stays
in the caller's page CSS or in the component's private geometry; it does not
become a shared argument. Stored tint ids and existing aliases keep their names.

## How it is built

- `Button.css` owns `.btn` and the four variant rules, the five size rules and
  the base defaults. `Button.jinja` maps each size name to its icon size and
  emits `btn-{variant}`, `btn-{size}` and `btn-{shape}`.
- `Pill.css` owns `.pill` and exactly the 21 variant rules listed above.
  `Pill.jinja` emits `pill-{variant}`.
- `Grid.css` owns `.grid-columns-2`, `.grid-columns-3`, `.grid-auto`,
  `.grid-flush` and `.grid-split`. `editorial/Document.css` owns
  `.grid.grid-document`. `main.css` owns `--sp-*` and `--grid-min-*`.
- `ButtonGroup.css` styles the group's own `button-group-{shape}` corners. That
  is a group argument, not a revival of the standalone `btn-{shape}` no-op.

### Evidence and corrections

- **Button sizes.** `xs` has production callers in `editorial/DrawingEditor`;
  `sm` and `md` are used across the pages, dialogs and layout. No production
  template passes `lg` or `xl`. The only literal `xl` outside the design kit is
  `tests/unit/jinja/test_button_groups.py`, which pins class emission.
- **Button variants.** All four have production callers: `primary` in
  `WorldNew`, `AdminDashboard`, `Settings`, `Login` and the dialogs; `secondary`
  across the pages, `Topbar` and `IconButton`; `text` in `WorldOverview`,
  `WorldNew`, `Rail`, `Topbar` and the editors; `danger` in `ImageEditor`,
  `DrawingEditor`, `ReportPanel` and the default confirmation dialog.
- **Pill variants.** The accepted set is unchanged. The decision brief stated
  that every variant has a real consumer; source shows ten are currently
  exercised only by the design kit and `tests/frontend/test_button_skin.py`:
  `info`, `accent`, `role-dev`, `npc`, `vermilion`, `cobalt`, `ochre`, `act1`,
  `act2`, `act3`. `info` appears as an `Alert` variant, not a Pill. The other
  eleven have product callers: `neutral` (default in the planning specimens),
  `success`, `danger`, `warning`, `role-admin`, `role-member`, `master`,
  `player`, `draft`, `plain`, `forest`.
- **Grid columns.** `Grid.css` defines only `columns=2` and `columns=3`.
  `columns=3` has no current caller; it stays because it is an implemented rule
  and the owner retained it. The design kit's `columns=2` callers are supported.
  The `columns=6` and `columns=8` in `Showcase.jinja` belong to
  `common.ChoiceGrid`, whose `--columns` variable and
  `repeat(var(--columns, 6), …)` rule support them. There are no `Grid`
  `columns=6/8` callers and no `grid-columns-6/8` rule, so no showcase layout
  correction is needed.
- **Grid gap.** Callers use `5`, `6` and `10`; the default is `6`. The supported
  list is every step that exists as a `--sp-*` token.

## Used by

- `common.Button`, `common.ButtonGroup`, `common.IconButton`,
  `common.MenuTrigger` and `common.ConfirmDialog`.
- `common.Pill` in the admin, world-members, story, row, docbar and planning
  surfaces.
- `common.Grid` in the world, character, NPC, place, story, session, page and
  showcase pages.

## Limits

- There is no runtime validation in this ticket. T19 owns the rejection and its
  diagnostics.
- No token or CSS is removed here. T20 owns the removal list, and this record
  retains `lg`, `xl`, `columns=3` and every Pill variant.
- T31 aligns the token hook with this record. The hook cannot tell a shared
  step written in `rem` from private geometry, so review owns that distinction.
- The design kit still shows `lg` and `xl`; its Buttons note marks them as
  experiments so the specimen does not imply they are product options.
