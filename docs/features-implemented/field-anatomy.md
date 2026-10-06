# Field anatomy

One M3 text field with two real variants — filled and outlined — wearing the
Root GDR atlas skin.

## What it does

- `common.Field` renders a semantic native `input`, `textarea` or `select`.
  There is no `div` dressed as a control.
- **Filled** keeps the label inside a tinted container; the label moves to the
  top when the field is focused or populated and the active indicator is the
  bottom rule.
- **Outlined** draws a full rule with a notch; the label rests inside the
  container and moves onto the rule (into the notch) when focused or populated.
- Supporting and error text stay below the container. Required, disabled,
  error, focus, populated, placeholder, select and textarea states are explicit.
- The label is a real `<label for>` associated with the control, and the error
  or helper text is wired through `aria-describedby` (`aria-invalid` on error),
  so the label and error semantics stay available to assistive technology.

## How it is built

- `common/Field.jinja` emits the label, the control, a decorative
  `<fieldset>/<legend>` notch and the supporting text. A `<select>` is always
  populated, so it floats the label from the start.
- **The notch technique is `fieldset`/`legend`.** The legend is hidden text
  whose width carves a real gap in the outline, so the label needs no
  background: the field looks right on paper, on a card and on any future
  surface. The legend is `aria-hidden`; the visible `<label for>` carries the
  association. The alternative — a background-clipped label — was rejected
  because the "hole" colour would have to match whatever surface the field sits
  on.
- **The rule is where the legend's center is.** Chromium paints a fieldset's top
  border at the legend's vertical center, not at the fieldset's own top edge, so
  the legend's height decides where the visible rule lands. The notch height is
  explicit (`--field-label-size-float + --sp-1`) and the outline is shifted up
  by half of it, which puts the rule exactly on the box's top edge where the
  floating label is centered. The component test asserts the label center, the
  legend center and the box top agree within 0.75px, so a font-metric or
  fieldset-rendering change cannot silently move the rule again.
- Floating is driven by `:focus-within` and `:placeholder-shown` (a single
  space placeholder is emitted when the caller gives none, so the selector
  always works). `prefers-reduced-motion` removes the label transition.
- `common/Field.css` owns `.field`. The legacy `.field`, `.field__label`,
  `.field__hint`, `.field__bar` and the generic `.input`/`.textarea`/`.select`
  rules left `main.css`, and the `field` entry left the selector-ownership
  allowlist, so the root has one owner again.
- The hint that used to be `.field__hint` is now the global `.hint` utility;
  it was never part of the component (it sits beside a `ButtonGroup`, an
  editor action bar and a members form).
- `common.Combobox` keeps its own ARIA listbox behaviour but borrows the field
  height, ink rule, atlas radius and focus colour, so there is no third
  text-control skin.
- Dimensions come from the M3 text-field spec; `--field-*` tokens live in
  `main.css` and are inventoried in
  `design-tokens/material3/text-fields.yaml`. The corner stays the atlas
  `--radius` and the focus stays the vermilion accent, recorded as web
  adaptations.

## Used by

- `pages.login.Login`, `pages.admin.InviteDialog`, `pages.worlds.WorldNew`,
  `pages.worlds.WorldSettings` (the add-player dialog), `pages.settings` and
  the `pages.showcase` specimens.

## Limits

- The label floats but does not animate its horizontal position; M3 keeps it
  left-aligned, which is what the atlas wants.
- `type="select"` floats the label immediately; a select with a placeholder-like
  empty option is not modelled.
- The notch is a `fieldset`/`legend` pair per outlined field. It is decorative
  and small, but it is one extra element per outlined control.
