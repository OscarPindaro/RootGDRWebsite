# Expressive buttons and button groups

`common.Button` and `common.ButtonGroup` provide reusable Material 3-inspired controls.

## What it does

- Buttons retain the editorial `primary`, `secondary` and `danger` colors and add `filled`, `tonal`, `outlined`, `elevated` and `text` configurations. Sizes run from `xs` to `xl`; buttons can be round or square, icon-only, selected, linked or block-width.
- A group without `options` arranges button children. A group with options renders native radio or checkbox inputs for single or multiple selection, including required and disabled states.
- Selection groups support arrow, Home and End navigation, Space, checked ARIA state and optional-radio deselection. Standard groups redistribute width while an item is pressed; connected groups change corners without changing width.
- User settings uses a required connected group for the symbol style. A change persists immediately and announces the result. Creation and world-settings links use compact icon-only buttons with accessible Italian labels.

## How it is built

- `common.Button` maps its API onto editorial color tokens and generated Material size, padding, icon and corner tokens.
- `common.ButtonGroup` renders native inputs. Its colocated script handles keyboard behavior, required-single protection, ARIA reflection and standard-group width compensation.
- Material's 0.9 damping and 1400 stiffness remain documented tokens. The web implementation uses the project's CSS easing because CSS has no portable stiffness/damping primitive. Reduced-motion preferences disable transitions.
- Settings receives typed `ButtonGroupOption` values and sends an htmx POST when the radio value changes; there is no separate save control.

## Notes and limits

- Groups are horizontal and may scroll in narrow showcase rows.
- Callers own submitted values and server-side validation.
- Icon-only choices need a meaningful group legend, a recognizable icon and an accessible label.
