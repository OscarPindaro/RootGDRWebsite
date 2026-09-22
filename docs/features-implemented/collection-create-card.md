# The collection create card

The literal creation affordance for a collection grid: one grid cell shaped like
an `editorial.Card`, dashed and empty, so it reads as the card that is not there
yet. F13 rolled it out to the grid collections and settled where creation lives
on every other collection.

## What it does

- `editorial.CollectionCreate` is a real `<button>` with a required `label` that
  reaches `aria-label`, so the keyboard and a screen reader reach it and it
  carries one clear name.
- It is one grid cell with an entity card's structure: a media area at the card
  media ratio where the picture would be, and a body box with the same padding
  where the name would be. Dashed ink border, transparent fill — the page
  background shows through.
- The shared entry owns the states and the action: hover is the entity cards'
  own lift onto a hard ink offset, focus is the atlas accent ring, pressing
  settles the lift back onto the page, and a `disabled` entry keeps its geometry
  and drops the `hx-post`. A page passes only the route, the label and the hint.
- Activating it reuses the existing draft-first POST route and lands in the same
  one-shot name editing. When a collection is empty and the role may create, the
  card *is* the collection, with a `hint` line instead of a separate empty panel.

## Placement

The card's contract is "the same size and structure as the cards beside it", so
it belongs where the neighbours are entity cards.

| Collection | Form | Creation lives | Why |
|---|---|---|---|
| Characters | card grid | the card | entity-card grid; creation is open to every reader |
| NPCs | card grid | the card (master only) | entity-card grid; creation is master-only |
| Places | atlas of rows | masthead command | a card would break the row rhythm |
| Sessions | ledger | masthead command | a card would break the ledger columns |
| Stories | story bands | masthead command | a card would not match the band |
| Pages | row list | masthead command | a card would break the row rhythm |
| Worlds | covers grid | masthead command | the neighbours are landscape covers, not entity cards |

The ledger, atlas, story-band and row collections were prototyped with the
literal card and rejected: a card in a ledger or atlas reads as a broken row and
damages scanning. The evidence is the placement table above and the F13 desktop
and phone screenshots of each collection, populated and empty. The create action
therefore stays a single deliberate masthead command on those pages.

Worlds is a grid, but of covers, not entity cards. The approved card is
portrait-media and entity-card-shaped; a cover is landscape-media with a
title/description/foot. An entity card in the covers grid would not line up, and
a cover-shaped creation cell would be a second implementation of the same idea —
work for F14, not a parallel `.cover--new`. Worlds keeps its masthead command
(the world create flow is a full form, not a draft-first POST).

## How it is built

- `editorial/CollectionCreate.jinja` — the button, its media and body slots, the
  `hx-post` to the caller's `action`, and a `disabled` state.
- `editorial/CollectionCreate.css` — the `collection-create` root. The media
  area reads `--media-ratio-portrait`, the same token the entity card's media
  uses, and the body repeats `.card__body`'s box so the two cards line up.
- `--collection-create-plus` sizes the plus; `--lift-shift` and `--lift-shadow`
  are the shared hard-offset hover the editorial cards use.
- `pages/characters/CharacterList.jinja` renders one card after the entity cards.
- `pages/npcs/NpcList.jinja` renders the card only for a master; an empty,
  readable collection for a player keeps the empty panel with no create entry.
- `common/EmptyState` stays for the collections whose create command is in the
  masthead and for the denied NPC case; it is not a second create affordance.

## Used by

- `pages.characters.CharacterList`, `pages.npcs.NpcList`, and the
  `pages/showcase` specimen.

## Limits

- Creation needs JavaScript. The masthead action it replaces was also htmx-only,
  and `GET /worlds/{id}/{kind}/new` deliberately redirects back to the list, so a
  plain link or form cannot create. F13 preserved that behaviour rather than
  adding a fallback.
- The card and an entity card are the same width and the same structure, so in a
  shared grid row they stretch to the same height. Alone in a row the card is
  its media plus its own body, which is shorter than an entity card carrying
  name, title and owner.
- The card is entity-card-shaped, so it only fits grids whose cells are entity
  cards. F14 owns extracting the repeated collection structures and deciding
  whether a cover-shaped creation cell is worth a variant.
