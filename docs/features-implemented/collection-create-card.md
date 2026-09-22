# The collection create card

The literal creation affordance for a collection grid: one grid cell shaped like
an `editorial.Card`, dashed and empty, so it reads as the card that is not there
yet.

## What it does

- `editorial.CollectionCreate` is a real `<button>` with a required `label` that
  reaches `aria-label`, so the keyboard and a screen reader reach it and it
  carries one clear name.
- It is one grid cell with an entity card's structure: a media area at the card
  media ratio where the picture would be, and a body box with the same padding
  where the name would be. Dashed ink border, transparent fill — the page
  background shows through.
- Hover is the entity cards' own lift onto a hard ink offset; focus is the
  atlas accent ring, independent of hover.
- Activating it reuses the existing draft-first POST route and lands in the same
  one-shot name editing. When a collection is empty the card *is* the
  collection, with a `hint` line instead of a separate empty panel.

## How it is built

- `editorial/CollectionCreate.jinja` — the button, its media and body slots, and
  the `hx-post` to the caller's `action`.
- `editorial/CollectionCreate.css` — the `collection-create` root. The media
  area reads `--media-ratio-portrait`, the same token the entity card's media
  uses, and the body repeats `.card__body`'s box so the two cards line up.
- `--collection-create-plus` sizes the plus; `--lift-shift` and `--lift-shadow`
  are the shared hard-offset hover the editorial cards use.
- `pages/characters/CharacterList.jinja` renders one card after the entity cards
  and no longer offers creation from the masthead.

## Used by

- `pages.characters.CharacterList`, and the `pages/showcase` specimen.

## Limits

- **Prototype.** F13 decides the grammar and F14 generalises or deletes this
  component; nothing else may adopt it before that.
- The card and an entity card are the same width and the same structure, so in a
  shared grid row they stretch to the same height. Alone in a row the card is
  its media plus its own body, which is shorter than an entity card carrying
  name, title and owner.
- Creation needs JavaScript. The masthead action it replaces was also htmx-only,
  and `GET /worlds/{id}/characters/new` deliberately redirects back to the list,
  so a plain link or form cannot create. This ticket preserved that behaviour
  rather than adding a fallback.
