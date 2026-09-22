# Symbol style: icons or shapes

An account preference chooses how role marks are drawn, and a successful change
is visible on every mark at selection time.

## What it does

- Every role (a navigation section, a content kind) has one semantic mark with
  two equivalent presentations: a linear icon and a solid shape. The server
  maps the role to both; the preference only picks which one is laid out.
- `symbol_style` lives on the user record. The first render of every page
  resolves it from `current_user.symbol_style`, so the reading page is correct
  with no JavaScript.
- On `/settings` the required connected `ButtonGroup` posts on change. When the
  response arrives, every visible role mark switches presentation immediately,
  without a reload or an extra Enter.
- The preference is account-wide and independent of the per-entity
  animal/shape/tint choices on a character or place; those are a different
  decision and are owned elsewhere.

## How it is built

- `common/Mark` renders **both** SVGs for its role and carries
  `data-mark-style` plus `mark--icons`/`mark--shapes`. `main.css` lays out only
  the class the server names, so a mark is still one grid item.
- `common/Mark.js` listens for `htmx:afterSwap`. `pages.settings.SettingsStatus`
  echoes the resolved style in a `data-symbol-style` attribute; Mark.js reads it
  and flips the class on every `[data-mark-style]` in the document. The value is
  the server's, not the browser's, and a failed request never swaps — so the
  marks keep the server's state.
- The two presentations are equivalent because they are resolved server-side
  from the same role in `backend/content/marks.py` (`BY_ROLE`). The client never
  invents a mark; it only chooses which of the two server-rendered SVGs to show.
- The form posts to `/settings` with htmx; without JavaScript it still posts
  natively, the enum is persisted, and the next render resolves the style from
  the user record.
- F18 gave the control a settings-page row: `pages.settings.Settings` puts the
  `ButtonGroup` in a labelled preference row under the **Aspetto** group, and
  the success message is a `common.Alert` with `role="none"` so the page's
  `#settings-status` region (`aria-live="polite"`) is the only announcer.

## Used by

- The rail (`layout.Rail`, `layout.RailItem`) and the world overview quick
  strip (`editorial.Quick`) render role marks with the resolved style.
- `pages.settings.Settings` owns the control; `users/views.py` persists it.

## Limits

- A mark ships both SVGs, so each mark's markup is roughly twice as large. The
  two are small inline paths and the alternative (re-fetching marks) is a
  network round trip.
- The flip covers marks already in the document. A mark that arrives in a later
  htmx fragment is rendered by the server with the persisted style, which is
  already correct.
- `.mark` and `.mark__svg` still live in `main.css` (the block they have always
  been in); the visibility rules were added there rather than in a new
  `common/Mark.css`, which would have made two stylesheets own the root.
