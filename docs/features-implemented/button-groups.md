# Expressive buttons and button groups

`common.Button` and `common.ButtonGroup` provide reusable expressive controls. They are demonstrated on `/components`; user settings use a connected, required single-selection group for the symbol preference.

## Buttons

`common.Button` keeps the existing `primary`, `secondary`, and `danger` editorial colors and the existing `sm`, `md`, and `lg` calls. It also provides `filled`, `tonal`, `outlined`, `elevated`, and `text` configurations mapped onto the same editorial palette. It adds:

- `size`: `xs`, `sm`, `md`, `lg`, or `xl` (32, 40, 56, 96, and 136px)
- `shape`: `round` or `square`
- `icon`, `icon_position`, and `icon_only`
- `selected`: emits toggle styling and `aria-pressed`
- `href` and `block`, as before

The size tokens use the Google-generated Material values: symmetric padding 12/16/24/48/64px, icons 20/20/24/32/40px, square corners 12/12/16/28/28px, and pressed corners 8/8/12/16/16px. Colors remain mapped to the site's editorial tokens.

## Groups

`common.ButtonGroup` has two rendering modes:

- Without `options`, it is an action group. Put `common.Button` children in its slot.
- With `options`, it renders a selection group backed by real radio or checkbox inputs.

Common properties are `label`, `variant` (`standard` or `connected`), `size`, and `shape`. Selection groups also accept `name`, `selection` (`single` or `multi`), `value`/`values`, and `required`. An option has `value`, optional visible `label` and `icon`, optional `aria_label` for icon-only choices, and optional `disabled`.

Standard groups use 18/12/8/8/8px gaps. Pressing an item expands its width by 15%, with the width removed evenly from its direct neighbors. Connected groups use a 2px gap and change corners without changing width. Their inner, pressed, and square outer corners follow the generated Material component tokens. The official 0.9 damping and 1400 stiffness are retained as tokens; CSS transitions use the project easing as the documented web adaptation because CSS has no portable stiffness/damping primitive.

The colocated script supplies optional-radio deselection, required-single protection, arrow/Home/End navigation, checked ARIA reflection, and standard-group width compensation. Native inputs retain form submission and Space-key behavior. Colocated CSS disables transitions when reduced motion is requested.

## Settings integration

The settings page receives typed `ButtonGroupOption` values from the backend. `Icone` and `Forme` share one required radio name, so exactly one remains selected. A change triggers an htmx POST immediately; the server persists the enum on the user and returns the Italian `Preferenza salvata.` alert into an `aria-live` status region. There is no separate save action.

Creation links on the world index, world overview, and the six content lists use compact icon-only `common.Button` instances. Their Italian labels remain available as `aria-label` values and tooltips, and existing hrefs and test ids are unchanged. World settings uses the same treatment with a settings gear.

## Limits

Groups are horizontal and may scroll in narrow showcase rows. Callers own submitted values and server-side validation. Icon-only options need a meaningful group legend and should use recognizable icons with an accessible label.
