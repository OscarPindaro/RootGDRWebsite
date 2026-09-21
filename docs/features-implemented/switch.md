# Switch

The only boolean control in the kit was `common.ButtonGroup` used as a
two-option choice. That reads as "pick one of these", not "turn this on", and
the accent preference (`frontend.md`) needs the second meaning.

## What it does

- An on/off setting built on a native `<input type="checkbox" role="switch">`,
  so keyboard, form submission and assistive technology need no JavaScript.
- The label names the control and is clickable; `helper` adds a line of
  explanation under it.
- `disabled` dims the track and takes the label out of the click path.

## How it is built

- Geometry is the M3 switch spec: a 52×32 track with a 2 dp outline and a
  handle that grows from 16 to 24 when on. The values live in
  `design-tokens/material3/switch.yaml` and are checked by
  `harness material check`.
- The M3 full corner is **not** adopted: the track and the handle take
  `--radius-sm`, recorded as a `web_adaptation` with its rationale.
- The 28 dp pressed handle is not adopted either, so pressing changes nothing;
  a test asserts the track width is stable on `pointerdown`.
- The handle's inset is derived from the tokens
  (`(track − handle) / 2 − outline`), so it is not a magic number.
- `prefers-reduced-motion` drops the transitions.

## Limits

- No icon inside the handle, and no "selected icon" state.
- No indeterminate state.
- Nothing in the product uses it yet: the accent preference it was built for is
  not in the user model, which still only carries `symbol_style`.
