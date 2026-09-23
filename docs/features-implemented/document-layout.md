# Document layout

Every content detail page — Character, NPC, Place, Story, Session, Page — lays
its document and its backlinks out with the same grid, so the six pages share
one breakpoint and one spacing contract.

## What it does

- `common.Grid` with `document` renders one main child and one optional aside
  stack: the document column, then the backlinks column at its right.
- Below 700px the aside stacks under the document and takes the full width.
- Prose keeps its readable measure (`--measure`, 68ch) whether or not the aside
  is there, so a document without backlinks does not stretch its lines to fill
  the vacated column.
- The backlinks panel is a direct child of the grid, not something nested inside
  the document column.
- A Story puts its included sessions and its backlinks in one aside stack rather
  than emitting two competing grid children.
- A Session keeps its pager in the document column, below the document.
- A Page puts `Altre pagine` and its backlinks in one aside.

## How it is built

- `common/Grid.jinja` takes `document`; `common/Grid.css` owns
  `.grid-document` — `minmax(0, 1fr) var(--grid-aside)`, the document gap, and
  the 700px collapse shared with the other auto-fit variants.
- `--grid-aside` and `--grid-document-gap` are alias tokens in `main.css`. The
  `.docpage` and `.article` grids and `.document { max-width: 900px }` are gone
  from `main.css`: the document is always a grid child now, so its own maximum
  width was dead.
- The document's own classes (`.document__head`, `.document__id`,
  `.document__page`, `.document__face`, the active-block rule and the phone
  fold) live in `editorial/Document.css`, a shared stylesheet the six detail
  pages declare. F22 moved them out of `main.css`; the image-editor override
  (`.document__face--editor`) moved there too, from `ImageEditor.css`, so
  `document` has one owner.
- `editorial.Links` renders the `.links` panel only. It used to render its own
  `<aside>`, which would have nested inside the aside stack that Story and Page
  need; the caller owns the stack, as the prototype does.
- `tests/frontend/test_document_layout.py` mounts all six real pages with
  constructed props and asserts the DOM contract (one main child, at most one
  direct aside) and the geometry (aside to the right at 800px and above, below
  the document at 390px).

## Used by

`pages/characters/CharacterDetail`, `pages/npcs/NpcDetail`,
`pages/places/PlaceDetail`, `pages/stories/StoryDetail`,
`pages/sessions/SessionDetail`, `pages/pages/PageDetail`.

## Limits

- The aside column keeps its width even when a page has no backlinks, so a
  document without them leaves that column empty rather than reclaiming it.
- The `document` variant is a plain grid: it cannot enforce "at most one aside".
  The DOM contract is asserted by the test, not by the component.
- The prototype defines two grids (`.docpage` at 700px, `.article` at 1100px).
  This ticket unified them at 700px and 16rem, so Page detail now collapses
  later and has a slightly wider aside than `prototypes/devin-prototype`.
- `nav.pager` still carries `margin-top: 2.5rem` as an inline style.
