# Document layout

Every content detail page — Character, NPC, Place, Story, Session, Page — lays
its document and its backlinks out with the same grid, so the six pages share
one reflow contract and one spacing contract.

## What it does

- `common.Grid` with `document` renders one main child and one optional aside
  stack: the document column, then the backlinks column at its right.
- The aside stacks under the document, at full width, when the document column
  can no longer hold both: the aside's 16rem plus the 34.75rem a 15rem portrait
  and a 17rem identity need. The decision follows the width the document is
  actually given, so 901px — where the shell hands its rail back and the page
  loses 276px — reflows exactly as 900px does.
- Both tracks can shrink, so the stacked children never sit on tracks wider
  than the grid: at 320px, or with a larger default text size, the aside track
  gives way instead of pushing the grid past the page.
- The portrait sits beside the identity only while the document column can hold
  a 15rem portrait, the head gap and a 17rem identity. Below that — a phone, or
  a 701px/901px/1024px page at 150% text — the portrait moves above the
  identity and stops at 13.75rem, so the identity keeps the whole column.
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

- `common/Grid.jinja` still takes `document` and emits the `grid-document`
  class; the tracks are the document page's own geometry, so
  `editorial/Document.css` owns `.grid-document` rather than `common/Grid.css`.
  All six detail pages declare that stylesheet, Page detail included.
- The document rules use `.grid.grid-document` — two classes — so they outrank
  `common/Grid.css`'s `.grid` for `gap` whichever stylesheet is collected
  first. `Grid.css` keeps only the primitive base and the other variants.
- `.grid.grid-document` sets `minmax(0, 1fr) minmax(0, var(--grid-aside))`, the
  document gap and `container-type: inline-size`; an inline-size container
  query at `53.75rem` spans both children across the tracks. The tracks stay
  defined, so a document without backlinks still keeps the aside column empty
  above the threshold, and the aside reaches its full 16rem as soon as the grid
  has room for it.
- A viewport breakpoint cannot express that reflow: above its own breakpoint the
  shell reserves 276px for the rail, so the same viewport width means two
  different document widths. `Grid.css` therefore no longer collapses
  `.grid-document` with the 700px auto-fit rule.
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
- The head reflows on the width the document gets, not on the viewport: the
  five pages that render a head mark their `.document` with `document--sized`,
  which registers a named `document-column` inline-size container, and a
  container query at `34.5rem` — a 15rem portrait, the 2.5rem head gap and a
  17rem identity — puts the portrait above the identity at 13.75rem wide. The
  threshold is in rem, so it grows with the reader's default text size instead
  of holding a rem-sized portrait beside an identity too narrow to read. The
  container is named so a caller that forgets the modifier does not silently
  measure the grid instead.
- `editorial.Links` renders the `.links` panel only. It used to render its own
  `<aside>`, which would have nested inside the aside stack that Story and Page
  need; the caller owns the stack, as the prototype does.
- `tests/frontend/test_document_layout.py` mounts all six real pages with and
  without related material and with a long title at 320, 390, 699, 700, 701,
  899, 900, 901, 1024, 1100 and 1440, and asserts the measure each column
  needs, that the tracks never exceed the grid, that the aside and the portrait
  never overlap the identity, that the title stays inside its column, and that
  the page never scrolls sideways. The measure is 17rem at the page's own
  computed text size, so the same assertion holds at 150%. A second matrix
  repeats the check on the read-only portrait at 390, 901 and 1440, a third
  mounts every page at 320 and 390 with a 150% text size, a fourth does the
  same at 701, 901 and 1024, and the existing DOM contract (one main child, at
  most one direct aside) still holds at a wide desktop.

## Used by

`pages/characters/CharacterDetail`, `pages/npcs/NpcDetail`,
`pages/places/PlaceDetail`, `pages/stories/StoryDetail`,
`pages/sessions/SessionDetail`, `pages/pages/PageDetail`.

## Limits

- Both reflows need `container-type: inline-size` and container queries. A
  browser without them keeps the two columns at every width; the application
  already relies on native `popover`, which shipped later than container
  queries in every engine it targets.
- Above the threshold the aside column keeps its width even when a page has no
  backlinks, so a document without them leaves that column empty rather than
  reclaiming it.
- The `document` variant is a plain grid: it cannot enforce "at most one aside".
  The DOM contract is asserted by the test, not by the component.
- The head needs the `document--sized` modifier. A page that copies the
  document markup without it keeps the portrait beside the identity at every
  width, because the named query does not match; the enlarged-text matrix fails
  on that, which is the guard for a new caller.
- The three portrait pages keep their body inside the identity column, so the
  body's measure follows the identity's (494px at 1440). The prototype spans
  the body across the document instead; that composition was not part of this
  correction.
- The prototype defines two grids (`.docpage` at 700px, `.article` at 1100px)
  and stacks the head at a 700px viewport. This layout unified the grids, so
  Page detail reflows at the document's measure rather than at 1100px, its
  aside is 16rem instead of 15rem, and the head stacks on the document's
  34.5rem instead of the viewport: at normal text a 699/700px page keeps the
  portrait beside a 396px identity instead of above it.
- `nav.pager` still carries `margin-top: 2.5rem` as an inline style.
