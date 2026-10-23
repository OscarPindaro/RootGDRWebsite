# Collection creation study

Bounded application-composed comparison for REQ-0019/T26. It renders the real
`pages.characters.CharacterList` through the application catalog and puts two
creation entries on the same DOM, the same typed fixture and the same real
creation button.

## Why this study

T26 asks where creation stays discoverable on a phone as a collection grows:
the retained creation card inside the grid, or a separate labelled entry above
it. The question is answered on real collection pages, not on a drawing. The
method is the application-composed mode approved in T22 and recorded in
[`docs/development_processes/prototyping.md`](../../docs/development_processes/prototyping.md);
T23's document exemplar is the template for the fixture, the raw page, the
inert boundary and the evidence, not part of this comparison.

The study does not change the product, add a route, or decide the treatment.
It produces the three collection examples T26 needs and measures the tradeoff.

## What is rendered

`study.py` builds a typed fixture and calls the real catalog with
`pages.characters.CharacterList`. The page is a raw full HTML document from the
catalog; the study adds one comparison strip, one stylesheet and one script. It
does not wrap the page in another shell.

Three collection states share one fixture definition:

| State | Published | Drafts |
|---|---|---|
| `empty` | 0 | 0 |
| `short` | 3 | 2 |
| `long` | 30 | 3 |

The cards use the approved demonstration cast from
`prototypes/devin-prototype/personaggi.html` (Rugginosa, Barone Talpa, Foglia di
Ferro, Corvinus, Mastro Tasso, Sibilla) and the reference draft
"Lo Scoiattolo Smemorato" from `seed/boschetto-di-smeraldo.yaml`. The long
collection repeats those names with a numeral and puts one long stress name on
the first card ("Rugginosa la Custode delle Mappe Rubate del Guado Spezzato" —
see `LONG_NAME` in `study.py`). Both are demonstration scaffolding, not campaign
content.

The pages are served on the ephemeral component server used by
`tests/frontend/`, not by the application. No database, campaign read, work
environment or showcase environment is involved.

## The two entries

Both options read the same DOM, the same cards, the same drafts and the same
`[data-testid="create-character"]` button. Switching never recreates a card and
never changes the fixture; it only moves the real button and changes the body
attribute the study stylesheet reads.

| | A · Retained | B · Compact above the grid |
|---|---|---|
| Entry | `editorial.CollectionCreate` as the last grid cell | The same button, moved before the grid |
| Widths | every width | below 700px only; above, A is unchanged |
| Empty collection | the dashed card is the collection, with the hint in its body | compact action with the same hint, empty grid below |
| Tap target (390px) | 350 × 476 (350 × 527 empty) | 350 × 58 (350 × 96 empty) |
| Desktop | unchanged | unchanged |

B is not the removed masthead plus: it is the same creation button, with the
same `hx-post`, the same accessible name and the same hint, in a labelled action
row above the collection. The study never adds a second creation control.

## Measurements

Phone profile 390×844, scroll position 0. "Scroll to entry" is the minimum
vertical scroll that brings the whole creation entry into view; "hint below
fold" is the same for the empty-collection hint. "Top actions" counts the visible
controls in the topbar and masthead plus the creation entry when it sits above
the first card. "Tabs" counts Tab presses from the page start to the creation
entry.

| State | Entry | First card top | Scroll to entry | Entry height | Hint below fold | Top actions | Tabs |
|---|---|---|---|---|---|---|---|
| empty | A | — | 331px | 527px | 313px | 6 | 11 |
| empty | B | — | 0 | 96px | 0 | 6 | 11 |
| short | A | 649px | 2039px | 476px | — | 5 | 14 |
| short | B | 727px | 0 | 58px | — | 6 | 11 |
| long | A | 649px | 17664px | 476px | — | 5 | 41 |
| long | B | 727px | 0 | 58px | — | 6 | 11 |

Desktop 1440×1000 is identical for A and B, because B is a phone-only
treatment: first card 413px, the long collection's entry 3077px below the fold,
tabs 51. Document height at 390px: empty 1231/1096, short 4156/3733, long
20331/19909 (A/B).

No state or option scrolls sideways at 320px or 390px; the focused test asserts
this for all six combinations. Both entries exceed the 44px touch target.

`evidence/measurements.json` holds the raw numbers for every captured state;
`capture.py` and the focused test read the same definition from
`study.MEASURE_JS`.

## Recommendation, decision left to the coordinator

The study recommends **B at phone widths, A retained at 701px and above**.

Why, in measured terms: with 30 entries the retained entry needs 17,664px of
scrolling and 41 Tab presses, while B is in the first screen and 11 Tab presses
away. Even when the collection is empty, A puts its explanatory hint 313px below
the first phone screen, while B shows it immediately. B keeps the same button,
label, hint and POST, and its 58px row is a valid touch target.

What B costs, and what choosing A buys:

- B adds one competing action at the top of a populated phone page (6 against
  5) and moves the first real card down by 78px, from 649px to 727px. The first
  card still starts inside the 844px screen.
- B loses the missing-card metaphor in the empty case: the page shows a compact
  action and an empty grid instead of a dashed card where the first character
  will appear. The hint carries the explanation.
- B is a breakpoint exception to the shared card model, so it is more code than
  A and must stay limited to the entity-card collections.
- A keeps one creation model everywhere, needs no new treatment, and keeps the
  card metaphor and the empty placeholder. Its cost is reachability as the
  collection grows and a below-the-fold explanation when empty.

The owner delegated the decision to the coordinator for this ticket. This
document records the comparison and the recommendation; it does not choose.
If B is selected, T27's boundary is the character and NPC collection
composition below 700px: move the existing button above the grid, give it the
compact row, keep the same POST and hint, leave desktop and every other
collection type unchanged, and do not restore the masthead plus. If A is
selected, T27 is an explicit no-change outcome.

The comparison does not settle appearance disclosure (T24), phone search (T28),
or creation on the ledger, atlas, story-band, row and cover collections, whose
masthead commands are out of scope.

## Simulation boundary

- The comparison strip says **Prototipo**, that the data is demonstration data,
  that saves are simulated and disabled, and that the comparison is not a
  product setting.
- The real creation button keeps `hx-post`, but it is `aria-disabled`, carries
  `data-prototype-inert="true"` and a title saying the save is disabled, and it
  stays in the tab order only so the keyboard path can be compared. Clicks,
  Enter, submits and non-GET htmx requests are blocked; no request leaves the
  page.
- Other write controls (the report dialog, logout, replay, forms) are disabled
  and labelled the same way. Navigation links are left as ordinary links; the
  study does not claim that following them works on the ephemeral server.
- The study never claims a saved state. Actual saved state is not part of this
  experiment.

## Run and verify

```console
uv run harness test frontend tests/frontend/test_collection_create_study.py
uv run python prototypes/collection-create-study/capture.py
uv run python prototypes/collection-create-study/capture.py --serve
```

The test proves the raw page and its real assets, equal cards/drafts/button
across the two entries, the different placement, the measured reachability,
the empty-collection explanation, the 44px touch targets, the 320/390 overflow
check, the labelled comparison, the inert boundary and no write requests. The
capture writes the twelve committed screenshots, `evidence/revisions.json` and
`evidence/measurements.json`.

`--serve` prints the ephemeral URLs (`/study/empty`, `/study/short`,
`/study/long`) and keeps the component server running so the owner can open a
state and switch A/B with the strip. Ctrl+C stops only that server. This mode
writes no evidence and does not start or read the application, its database or
the work/showcase environments.

## Evidence

Desktop 1440×1000 and phone 390×844, one image per state and entry:

| State | A | B |
|---|---|---|
| empty | [`desktop-empty-a.png`](evidence/desktop-empty-a.png) · [`phone-empty-a.png`](evidence/phone-empty-a.png) | [`desktop-empty-b.png`](evidence/desktop-empty-b.png) · [`phone-empty-b.png`](evidence/phone-empty-b.png) |
| short | [`desktop-short-a.png`](evidence/desktop-short-a.png) · [`phone-short-a.png`](evidence/phone-short-a.png) | [`desktop-short-b.png`](evidence/desktop-short-b.png) · [`phone-short-b.png`](evidence/phone-short-b.png) |
| long | [`desktop-long-a.png`](evidence/desktop-long-a.png) · [`phone-long-a.png`](evidence/phone-long-a.png) | [`desktop-long-b.png`](evidence/desktop-long-b.png) · [`phone-long-b.png`](evidence/phone-long-b.png) |

`evidence/revisions.json` records the base commit, the blob hashes of the real
components the page renders, the fixture identifiers and the capture viewports.
The captures describe that revision; the components are live and a later change
moves them, so these images are not a frozen reference.

## What this revision shows

Compared with `prototypes/devin-prototype/personaggi.html` at 390px: the same
atlas shell, serif names, portrait media and dashed creation card. The study
does not reuse the prototype's static shell; the shell and the list come from
the real catalog.

- At 390px, A keeps the create card after the last published card; with 30
  entries it is about 21 screens below the first one. B puts the compact action
  above the grid, so the collection starts 78px lower and the entry is always
  in the first screen.
- At 390px with no characters, A's dashed card is 527px tall and its hint is
  below the first screen; B's action is 96px and its hint is visible.
- At 1440px the two captures are the same page: the compact treatment is
  deliberately phone-only.

## Files

- `study.py` — typed fixture, three collection states, the raw catalog render,
  the shared measurement expression and the source revisions.
- `comparison.css` — the prototype strip and the phone-only compact entry.
- `comparison.js` — entry switching, the DOM move and the inert write boundary.
- `controls.html` — the labelled comparison strip and the state links.
- `capture.py` — desktop/phone captures, measurements and the interactive
  `--serve` entry point on the ephemeral server.
- `evidence/` — committed screenshots, `revisions.json`, `measurements.json`.
