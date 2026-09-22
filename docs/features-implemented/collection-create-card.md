# Collection create card

The disputed visual direction for a collection's creation affordance: a literal
card in the grid instead of a masthead plus. **F12 is a prototype awaiting
visual approval; F13/F14 own deleting or generalising it and rolling it out.**

## What it does

- Renders the creation action as one grid cell beside the entity cards — the
  warm paper surface, an ink border, and a stable square plus.
- Reuses the existing draft-first POST route (`/worlds/{id}/characters/new`), so
  activating it persists a draft and lands in the one-shot name editor exactly
  as the masthead plus did.
- Is a real `<button type="button">` with a required `label` that becomes its
  accessible name; focus is visible and hover changes the surface without
  moving the card.
- Carries an optional `hint` line. On Characters the hint is used only when the
  collection is empty, so the create card *is* the empty collection instead of
  an empty panel with a second action beside it.

## How it is built

- `editorial.CollectionCreate.jinja` takes `action`, `label` and `hint`. It is
  named for the collection grammar, not for characters, because F13/F14 will
  generalise it.
- `editorial/CollectionCreate.css` owns the `collection-create` root. It is one
  grid cell because it is a plain grid child of `common.Grid min="card"`, the
  same grid the entity cards use; the row stretches it to the tallest card.
- Two alias tokens in `main.css` hold the only raw numbers:
  `--collection-create-min-height` (the empty collection's presence) and
  `--collection-create-plus` (the square plus, matching the prototype).
- It declares its own stylesheet with `{#css #}`; the page's directive lists it
  too, so an htmx swap carries the CSS.
- The button is an htmx POST with `hx-swap="none"`, mirroring the masthead plus.
  **No-JavaScript behaviour is unchanged, and was already absent:** the POST
  route always answers `204` with an `HX-Redirect` header, so a plain form or
  link cannot create today either. The GET `/characters/new` route is a
  non-mutating redirect by design.

## Used by

- `pages.characters.CharacterList` only. F12 deliberately touches no other
  collection; the prototype exists so the direction can be judged before F13
  applies it anywhere else.

## Limits

- Prototype scope: one caller, one shape, no `size`/`variant` props.
- The empty-state hint is a single optional line; there is no separate title.
- The masthead plus on Characters is removed for the comparison, so the card is
  the only creation affordance there. Every other collection keeps its masthead
  plus until F13.
