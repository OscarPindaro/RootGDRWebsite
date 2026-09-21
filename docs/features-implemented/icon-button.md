# IconButton

An icon-only action needs a name even though it shows none. `common.Button`
could already render `icon_only`, but nothing forced the label to exist and the
default shape was the round one.

## What it does

- Renders an icon-only action whose `label` is required and reaches both
  `aria-label` and the tooltip, so the accessible name and the visible hint
  cannot drift apart.
- Square by default (`shape="square"`), which is the shape the product uses for
  commands.
- Keeps the caller's attributes (`data-testid`, `hx-post`, `class`) on the
  button, not on the wrapper.
- Renders an anchor when `href` is given.

## How it is built

- It is a composition, not a new control: `common.Tooltip` around
  `common.Button` with `icon_only` and `shape="square"`. Button keeps the CSS
  and the states; IconButton adds the label obligation and the square default.
- Caller attributes are forwarded with `_attrs={{ attrs }}`, the supported
  JinjaX way, so `Button` merges them into its own class and style.
- No CSS of its own: the appearance comes from `Button.css` and `Tooltip.css`,
  which the component declares with `{#css #}` so an htmx-loaded fragment
  carries them.

## Used by

- The world overview masthead (new session, world settings).
- `editorial.ImageEditor`: the history command is now an IconButton placed
  **under** the image instead of on top of it (feedback points 4 and 11).

## Limits

- The tooltip is the only visible hint; a destructive action still needs a
  confirmation somewhere else.
- `selected` renders `aria-pressed`, which is a toggle. For a radio-like choice
  use `common.ButtonGroup`.
