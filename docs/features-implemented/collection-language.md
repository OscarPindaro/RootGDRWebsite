# The collection language

One vocabulary for the list pages: a character is an entity card, a story is a
band, a session is a ledger row, a place is an atlas row. They share their
interaction and state rules and keep their own density.

## What it does

- **`editorial.EntityCard`** (`.entity-card`) is the portrait card for a
  character, NPC or draft place. It replaced `editorial.Card`, whose `.card`
  root collided with the generic `common.Card` container. An NPC card takes
  `npc` and shows the NPC badge and the dashed owner rule.
- **`editorial.StoryCard`** (`.story-card`) is a story band: the act strip names
  the status and the period, the body carries the title and summary, and the
  foot the session count and the draft state. `level` keeps the heading in the
  page outline (2 on the list, 3 in the overview column).
- **`editorial.StoryBand`** (`.story-band`) is the strip alone, reused `inline`
  as the status badge on the story document.
- **`editorial.Ledger`** (`.ledger`) and **`editorial.LedgerRow`**
  (`.ledger__row`) are the session and page collections: a fixed four-column
  grid, a header row of labels, and records with a number, a date/slug, the
  record itself and a tag. `sdot` adds the session tint dot, `meta_extra` the
  second date line.
- **`editorial.RowList`** (`.row-list`) and **`editorial.Row`** (`.row`) are the
  place atlas and the draft lists: a mark (the caller's content), a name and
  description, and a meta cell. `draft` marks the row with the shared draft
  pill.

## Shared rules, per-representation density

`editorial/Collection.css` owns what the representations share:

- `.collection-surface` — the openable hard-offset hover. The offset and the
  shadow are `--lift-shift` / `--lift-shadow`, the tokens F12 added; pressing
  settles the card back onto the page. Applied to the entity card, the story
  card, the create card, the world cover and the overview's current-scene row.
- `.collection-meta` — the metadata line: mono and muted. Applied to a card's
  owner, a story's foot, a ledger number and tag, and a row's meta.
- Focus is the one global `:focus-visible` rule in `main.css`; every openable
  surface uses it. The create card no longer overrides it, so all of them ring
  the same way.
- The ledger row and the row use a quiet background highlight, not the lift: a
  record is not a card.

Density stays with each component: `Ledger.css` keeps the four columns and the
phone fold, `StoryCard.css` the band, `Row.css` the row rhythm, `EntityCard.css`
the portrait media and the body box. The create card mirrors the entity card's
media ratio (`--media-ratio-portrait`) and body box so the two line up in a grid.

## How it is built

- `editorial/EntityCard.jinja/.css`, `StoryCard.jinja/.css`,
  `StoryBand.jinja`, `Ledger.jinja`, `LedgerRow.jinja`, `Ledger.css`,
  `RowList.jinja`, `Row.jinja`, `Row.css`, `Collection.css`.
- `main.css` gave up the `.card*`, `.story*`, `.ledger*`, `.sdot`,
  `.rowlist`/`.row*` families and their phone rules; the `.feature` and
  `.wherenow` one-offs stayed there until F22, which moved `.cover` and `.quick`
  into their components and `.feature`/`.wherenow` into the page CSS beside
  `pages.places.PlaceList` and `pages.worlds.WorldOverview`.
- `common.Card` stays the generic M3 container, used by Login, the world list's
  empty panel and the showcase. `pages.worlds.WorldCard` was unused and is gone.
- The ownership guard watches the new roots and `MIGRATION_ALLOWLIST` is empty.

## Used by

- `pages.characters.CharacterList`, `pages.npcs.NpcList`,
  `pages.places.PlaceList` (drafts), `pages.sessions.SessionList`,
  `pages.stories.StoryList`, `pages.pages.PageList`,
  `pages.worlds.WorldOverview`, `pages.stories.StoryDetail`, the showcase.

## Limits

- The shared `.collection-meta` rule sets family and colour, not size: the
  ledger's dense columns and a card's owner label keep their own sizes.
- The ledger and row phone folds are per-representation; there is no shared
  responsive rule beyond "keep the columns readable".
- `editorial.RowList` is a one-line wrapper. It exists so `.row-list` has one
  owner and the four callers cannot drift; it carries no behaviour.
