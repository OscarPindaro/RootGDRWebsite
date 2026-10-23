# Component vocabulary

The finite set of public options an author may pass to `common.Button`,
`common.Pill` and `common.Grid`, and the rule for extending it. The project
owner delegated the choice to the coordinator on 2026-10-23; this record is the
accepted outcome for REQ-0019/T18 and the input for T19, T20 and T31.

REQ-0019/T20 audited every option and token the 2026-10-21 review named. No
component option was removed: `lg`, `xl`, the standalone `shape` argument and
the ten design-kit-only Pill variants all keep their implemented CSS and their
specimens. Three dead alias tokens were removed; every other candidate is
retained with the consumer or the documented reason recorded below.

REQ-0019/T19 enforces the finite choices in this record when a component
renders. An undeclared value stops the render with a diagnostic naming the
component, the argument and the value instead of producing a class no
stylesheet matches. The check covers only the arguments listed below; native
HTML attributes and the reserved `shape` no-op keep their current behavior.

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
it would ripple without a visible change. The T20 audit below records the
consumers behind each retained option.

### Decision ownership

| Decision | Owner | Consequence |
|---|---|---|
| The supported, experimental and reserved options above | Project owner; delegated to the coordinator on 2026-10-23 | Authors use this list; T19 enforces it |
| Rejecting an unsupported value | T19 | Render-time rejection by `component_option`; the message names the component, argument and value |
| Removing unused or experimental surface | T20, only from this record | A retained option stays even when no caller uses it |
| Token checks and private geometry | T31, following "Private geometry" below | A local rem/clamp value is not a token violation |
| Stored tint ids and live aliases | Project owner | `--p1`–`--p12`, `tint="p8"`, `tint="ochre"` and the alias names are not renamed for consistency |
| Adding a public option | Project owner | The extension rule below applies |

### Machine-checked list

`tests/frontend/test_component_vocabulary.py` reads this block and compares it
with the component templates, their stylesheets, the spacing and grid tokens in
`main.css`, and the design-kit callers. It also reads the T20 audit block below,
so a retained option cannot lose its last consumer unnoticed.

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

### T20 audit

The audit checked stylesheets, templates, component and page scripts, the
design-kit specimens and the spacing/grid tokens before changing anything. It
includes `var()` lookups, JavaScript and template interpolation, and the two
dynamic size loops in `Showcase.jinja`. A value has a consumer when one of those
places reads it; a value with no reader was either removed or retained for a
recorded reason.

| Candidate | Consumers found | Outcome |
|---|---|---|
| Button `lg`, `xl` | `.btn-lg`/`.btn-xl` and their `--button-height-*`, `--button-padding-*`, `--button-icon-*` tokens; the matching `ButtonGroup` rules and tokens; both design-kit loops over `["xs", "sm", "md", "lg", "xl"]`; `tests/unit/jinja/test_button_groups.py` renders `xl`. No production caller. | Retained as design-kit experiments. |
| Button `shape` | `Button.jinja` emits `btn-{shape}`; `Topbar`, `MenuTrigger` and `IconButton` pass `square`; `round` is the default; `ButtonGroup.jinja` emits `btn-{shape}` on its items and `Showcase.jinja` passes `square` to a group and shows the standalone specimen. No stylesheet styles the standalone `btn-round`/`btn-square`; `ButtonGroup.css` styles the group's corners. | Retained as a reserved no-op. |
| Pill `info`, `accent`, `role-dev`, `npc`, `vermilion`, `cobalt`, `ochre`, `act1`, `act2`, `act3` | `Showcase.jinja` renders every one; `tests/frontend/test_button_skin.py` pins each fill token and its 4.5:1 contrast. No product caller. | Retained; the design kit is their contract. |
| `--ok` | No stylesheet, template, script or specimen reads it. `docs/frontend_guide.md` names it in the identity-token list; the standalone prototype defines its own copy. | Retained: the guide is the documented contract, and its T21 rewrite keeps the name. Removing the token would leave the guide naming an absent value. |
| `--clr-surface-raised` | No code reader. `docs/jinjax.md` names it as the light surface a component must not hardcode when it can render on both paper and rail. | Retained for the same guide reason; the T21 rewrite keeps the name. |
| `--clr-overlay` | No reader in any stylesheet, template, script, test or specimen. | Removed. |
| `--status-danger-light` | No reader; its value duplicates `--vermilion`/`--p1`, but the alias itself was unused. | Removed. |
| `--radius-xl` | No reader; the other radius steps are used. | Removed. |
| `--clr-nav-accent` | No reader. It is a semantic role alias and is not on the review's candidate list. | Retained and reported to the coordinator; it is outside T20's approved removal list. |

Removing the three aliases cannot change a rendered style: no declaration,
template, script or specimen referenced them, so no computed value depends on
them. `--ok`, `--clr-surface-raised` and `--clr-nav-accent` are the only unread
aliases left; the first two exist because a central guide names them, and the
third is outside the approved list.

<!-- component-vocabulary-audit:start -->
```text
pill.design-kit-only: info accent role-dev npc vermilion cobalt ochre act1 act2 act3
grid.columns.no-caller: 3
token.removed: --clr-overlay --status-danger-light --radius-xl
token.retained: --ok --clr-surface-raised --clr-nav-accent
```
<!-- component-vocabulary-audit:end -->

`tests/frontend/test_component_vocabulary.py` reads this block. It fails if a
documented option loses its last consumer without a recorded retention, if a new
option is added without a caller or specimen, or if a removed token comes back.

### Enforced values

`Button.jinja`, `Pill.jinja` and `Grid.jinja` check their finite arguments at
render time, after `{#def#}` and before they build a class. Each template calls
the `component_option` Jinja global in a `{% do %}`:

```jinja
{% do component_option("common.Button", "variant", variant, "primary", "secondary", "text", "danger") %}
```

The check covers exactly the finite choices above: Button `variant` and `size`
(including the experimental `lg` and `xl`), Pill `variant`, and Grid `columns`,
`gap` and `min`. `Grid.columns` and `Grid.min` are checked only when the caller
sets them; `gap` has a default. The standalone `shape` argument is not checked:
it is the documented no-op. Native HTML attributes, `class`, `data-*` and
`aria-*` still pass through `attrs` untouched. A Jinja expression is checked
with the value it produces at render time, so a valid computed value keeps
working and an invalid one fails at the same point as a literal.

A rejected value raises `backend.jinja.ComponentOptionError` and the render
stops; no markup is produced. The message names the component, the argument and
the value, then lists the accepted values:

```text
common.Button: argument 'variant' does not accept 'ghost'; expected one of: primary, secondary, text, danger
```

The error is an ordinary render failure: the application answers with a 500 and
the server log carries the message, rather than serving a class no stylesheet
matches. `tests/unit/jinja/test_component_options.py` renders every documented
value and pins the rejection for an invented Button or Pill variant, Grid
`columns=4`, an absent spacing step and an unknown minimum.

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
- `backend/jinja.py` registers `component_option` on the catalog. The three
  component templates call it in a `{% do %}`; it raises
  `ComponentOptionError` for a value outside the accepted list. The choices are
  declared in the template next to the argument they bound, and
  `test_component_options.py` renders every value in this record, so the
  template list and the manual cannot drift.

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
- **Design-kit loops.** `Showcase.jinja` has two
  `{% for group_size in ["xs", "sm", "md", "lg", "xl"] %}` loops. Each passes
  `:size` to the `ButtonGroup` and to every `Button` in the group, so `lg` and
  `xl` have a dynamic template consumer even though no product page uses them.
  The audit test reads the literal list and fails if a size leaves it.
- **Token aliases (T20).** The review named five no-reference aliases. Three had
  no reader anywhere and were removed: `--clr-overlay`, `--status-danger-light`
  and `--radius-xl`. `--ok` and `--clr-surface-raised` have no code reader either,
  but `docs/frontend_guide.md` and `docs/jinjax.md` name them; removing them
  would leave those guides describing absent values, so they stay and the T21
  rewrite keeps both names. `--clr-nav-accent` is also unread, but it is a
  semantic role alias and was not on the review's candidate list; it is reported
  rather than removed.

## Used by

- `common.Button`, `common.ButtonGroup`, `common.IconButton`,
  `common.MenuTrigger` and `common.ConfirmDialog`.
- `common.Pill` in the admin, world-members, story, row, docbar and planning
  surfaces.
- `common.Grid` in the world, character, NPC, place, story, session, page and
  showcase pages.

## Limits

- The finite choices are enforced when a component renders. There is no static
  or pre-commit value check: the `template-types` checker still checks prop
  names and types, not the values of these three arguments, so an invalid
  literal in a branch that never renders is not reported before the request.
- Only Button `variant`/`size`, Pill `variant` and Grid `columns`/`gap`/`min`
  are checked. `ButtonGroup.button_variant` and `ChoiceGrid.columns` are
  separate arguments with their own rules and keep their current behavior.
- The standalone Button `shape` argument is accepted without a value check. It
  stays the documented no-op, so `round` and `square` keep rendering the same
  unstyled class.
- T20 removed no component option. It removed only the three unread aliases
  `--clr-overlay`, `--status-danger-light` and `--radius-xl`; `lg`, `xl`,
  `columns=3`, the standalone `shape` argument and every Pill variant stay.
- `--ok`, `--clr-surface-raised` and `--clr-nav-accent` remain. The first two are
  named by central guides, and the T21 rewrite keeps both names; the third is a
  semantic role alias outside the approved removal list.
- T31 aligned the token hook with this record: it guards palette and shared
  measures, allows a component's own rem/em/clamp geometry, and cannot by itself
  tell a shared step written in `rem` from private geometry, so review owns that
  distinction.
- The design kit still shows `lg` and `xl`; its Buttons note marks them as
  experiments so the specimen does not imply they are product options.
