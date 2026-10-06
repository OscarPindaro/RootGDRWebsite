# Tint picker

The compact control for a document's tint: the current swatch and its name on
the trigger, the twelve-tint palette in a popover.

## What it does

- `editorial.TintPicker` shows a swatch and the tint's Italian name
  (`Vermiglio`, `Bosco`, `Cobalto`, …). Clicking it opens a radio palette; the
  chosen swatch is marked by a ring and a check as well as its colour, and every
  swatch carries its name as the radio's label.
- The value is the canonical `p1`–`p12` string the API stores. The popover's
  open state is never document state: choosing closes the panel and repaints the
  trigger immediately, while persistence belongs to the autosave integration.
- Escape, light dismiss and the focus return come from the native popover; the
  panel keeps its bounds inside the viewport, and the palette keeps 44px targets
  on phone. A disabled or read-only document renders a disabled trigger.

## How it is built

- `editorial/TintPicker.jinja` renders the trigger (`popovertarget`) and the
  panel; the panel reuses `common.ChoiceGrid` with `kind="tint"` and borrows
  `common/Menu.js` for positioning only — its keyboard model is the radio
  group's own, not a menu's.
- `editorial/TintPicker.js` keeps the local behaviour: a radio choice repaints
  the trigger and writes the canonical field the caller passes in the content
  slot; a change on that field (a restored draft, a server refresh) repaints the
  radios and the trigger.
- `editorial/Metadata` renders `kind="tint"` with the picker plus one hidden
  input, so the autosave registers a single field instead of twelve competing
  radios.
- The living kit shows the control next to the other choice grids.

## Limits

- The palette is a popover, not a dialog: it is not focus-trapping and closes on
  light dismiss. Inside a modal it closes itself before its parent.
- The control does not persist anything on its own; without the metadata
  integration it is a local preview.
