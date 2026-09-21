# Tabs

Two views of the same thing — the `Scrivi` / `Anteprima` pair a document needs —
were only expressible with `common.ButtonGroup`, which reads as a set of
buttons. The document layout wants a strip.

## What it does

- A tab strip: `items` (the same `ButtonGroupOption` the button groups take),
  a `name`, the selected `value`, and an optional `label` for the group.
- The panels are the caller's content: each panel carries
  `data-tabs-panel="<value>"` and the colocated script shows the selected one.
- The selected tab is marked by the accent rule under its label, not by a shape
  change.

## How it is built

- It is a **native radio group**, not a hand-built ARIA tablist. The browser
  owns the keyboard model (arrows, Home/End) and the group semantics, and the
  script only toggles `hidden` on the panels. A real `role="tablist"` would
  have meant reimplementing that model for no gain here.
- `common/Tabs.js` re-syncs on `htmx:afterSwap`, like the button group.
- `--rule-width-strong` (2px) is the indicator's weight, a token added for the
  strong rules of the atlas.

## Limits

- The strip does not lazy-load or preserve a panel's state; both panels exist
  in the DOM and the inactive one is `hidden`.
- No scrollable/overflowing tab strip.
- The panel ids are not linked to the tabs with `aria-controls`, because the
  panels come from the caller. The group legend names the choice instead.
