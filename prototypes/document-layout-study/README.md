# Document layout study

Bounded application-composed comparison for REQ-0019/T23. It renders one real
`pages.characters.CharacterDetail` document through the application catalog and
puts two document arrangements on the same DOM and the same typed fixture.

## Why this study

The owner-provided bookkeeping study compares an open and a flipped NPC
reference. Those are two presentations of a reference card, not two document
arrangements, so they do not satisfy T23's comparison. This study is the one
bounded document exemplar T23 asks for; it does not add a preview framework,
a route in the application, or a second prototype system.

The method is the application-composed mode approved in T22 and recorded in
[`docs/development_processes/prototyping.md`](../../docs/development_processes/prototyping.md).
The page uses the real catalog, shell, assets and controls. Comparison CSS,
controls and evidence stay in this folder.

## What is rendered

`study.py` builds a typed fixture and calls the real catalog with
`pages.characters.CharacterDetail`. The fixture is the retained Rugginosa
specimen from `prototypes/devin-prototype/personaggio.html`: name, title,
summary, body, tint, animal, related links and appearance choices. The page is
a raw full HTML document from the catalog; the study adds one comparison strip,
one stylesheet and one script. It does not wrap the page in another shell.

The page is served on the ephemeral component server used by
`tests/frontend/`, not by the application. No database, campaign read, work
environment or showcase environment is involved.

## The two arrangements

Both arrangements read the same DOM, the same fixture and the same real
controls. Switching only changes `data-study-layout` on `<body>`.

| | A | B |
|---|---|---|
| Head | Portrait beside identity, as the application renders it | Portrait beside identity |
| Body | Inside the identity column, beside the portrait | Full document width, below the portrait column |
| Backlinks | Aside to the right, or below when the grid cannot fit it | Unchanged |
| Appearance choices | In the portrait column | In the portrait column |

Arrangement B is the "body below the compact portrait/identity header"
alternative from the frontend review. The portrait column still carries the
real appearance controls, so B's head is not shorter than A's; the difference
is the body's width and starting point. Appearance disclosure is T24's
decision and is not made here.

## Simulation boundary

- The comparison strip says **Prototipo**, that the data is demonstration data,
  that saves are simulated and disabled, and that the comparison is not a
  product setting.
- Every real write control is disabled or `aria-disabled`, carries
  `data-prototype-inert="true"` and a title saying the save is disabled. Form
  submits, non-GET htmx requests, clicks and edit gestures are blocked.
- The appearance choices and the image surface are visible but inert. No file
  is uploaded, no autosave runs and no campaign data is read or written.
- The study never claims a saved state. Actual saved state is not part of this
  experiment.

## Run and verify

```console
uv run harness test frontend tests/frontend/test_document_study.py
uv run python prototypes/document-layout-study/capture.py
uv run python prototypes/document-layout-study/capture.py --serve
```

The test proves the raw page, the real stylesheets, equal data and DOM across
the two arrangements, the different body geometry, the labelled comparison,
the inert controls and the absence of write requests. The capture writes the
four committed screenshots and `evidence/revisions.json`.

`--serve` prints an ephemeral URL and keeps the component server running so the
owner can open the page and switch A/B with the strip. Ctrl+C stops only that
server. This mode writes no evidence and does not start or read the
application, its database or the work/showcase environments.

## Evidence

| Viewport | A | B |
|---|---|---|
| Desktop 1440×1000 | [`evidence/desktop-a.png`](evidence/desktop-a.png) | [`evidence/desktop-b.png`](evidence/desktop-b.png) |
| Phone 390×844 | [`evidence/phone-a.png`](evidence/phone-a.png) | [`evidence/phone-b.png`](evidence/phone-b.png) |

`evidence/revisions.json` records the base commit, the blob hashes of the real
components the page renders, the fixture identifiers and the capture viewports.
The captures describe that revision; the components are live and a later
change moves them, so these images are not a frozen reference.

## What this revision shows

Compared with `prototypes/devin-prototype/personaggio.html` at 1440px and
390px: the same atlas shell, portrait/identity head, serif prose and related
links. The study does not reuse the prototype's static shell; the shell and
the document come from the real catalog.

- At 1440px, A places the body in the identity column beside the portrait; B
  places it at the full document width below the portrait column. B is taller
  and starts the body lower, and its prose measure is wider.
- At 390px, both arrangements stack in the same order: portrait and appearance
  choices, identity, body, backlinks. The comparison does not change the phone
  reading order.
- No arrangement is declared the owner's choice. T24 and T26 use the approved
  mode for their own decisions; T23 records the method and this exemplar.

## Files

- `study.py` — typed fixture, catalog render and source revisions.
- `comparison.css` — the prototype strip and arrangement B.
- `comparison.js` — layout switching and the inert write boundary.
- `controls.html` — the labelled comparison strip.
- `capture.py` — desktop/phone captures and the interactive `--serve` entry
  point on the ephemeral server.
- `evidence/` — committed screenshots and `revisions.json`.
