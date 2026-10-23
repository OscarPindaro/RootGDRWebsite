# Phone appearance study

Bounded application-composed comparison for REQ-0019/T24. It renders one real
`pages.characters.CharacterDetail` document through the application catalog and
puts two phone arrangements of the same appearance controls on the same DOM and
the same typed fixture.

Mode: application-composed, approved on 2026-10-21 (T22) and demonstrated by
T23. This study is dated 2026-10-23.

## Why this study

The review captures at 390px show the editable character as portrait, image
history, animal, tint, then the identity heading. The owner asked whether those
appearance controls should stay always visible above the identity or move behind
an explicit disclosure. This study builds both from one DOM so the comparison is
about the arrangement, not about different content or different controls.

The method is the application-composed mode approved in T22 and used by T23. The
page uses the real catalog, shell, assets and controls. Comparison CSS, the
comparison-only disclosure and the evidence stay in this folder.

## What is rendered

`study.py` builds a typed fixture and calls the real catalog with
`pages.characters.CharacterDetail`. The fixture is the Fiamma Rossa specimen
from the 390px review captures: name, title, summary, body, tint (`p8`), animal
(`🦊`), one related place and the real appearance choices. The page is a raw
full HTML document from the catalog; the study adds one comparison strip, one
stylesheet and one script. It does not wrap the page in another shell.

The page is served on the ephemeral component server used by `tests/frontend/`,
not by the application. No database, campaign read, work environment or showcase
environment is involved.

## The two arrangements

Both arrangements read the same DOM, the same fixture and the same real
controls. Switching only changes `data-study-appearance` on `<body>`. The
disclosure button is inserted once in both arrangements; option A hides it.

| | A · Always visible | B · Explicit disclosure |
|---|---|---|
| Portrait | Visible, 220×275 at 390px | Visible, 220×275 at 390px |
| Image history | Visible under the portrait | Inside the disclosure |
| Animal and tint | Visible under the history | Inside the disclosure |
| Disclosure target | — | Visible under the portrait, 220×51 |
| Identity heading | After all appearance controls | After portrait and disclosure |
| Desktop | Unchanged | Unchanged; the disclosure is phone-only |

Option B applies only where the corrected document head stacks the portrait
above the identity (`@container document-column (max-width: 34.5rem)`). At
desktop the head is two columns, the disclosure is not rendered visibly, and the
appearance controls stay in the portrait column exactly as A.

The disclosure is a real `button` with the atlas button skin, `aria-expanded`
and `aria-controls` for the history row and the choices. It sits between the
portrait and the controls it reveals. Opening and closing it changes no form,
URL, version or selection.

## Measurements

Taken on the committed captures at 390×844 and 320×844, Chromium, 1× device
scale. "Document start" is the top of `.document`, below the unchanged docbar;
"product content" is the top of `#main`; "page top" includes the prototype strip.
The identity is the `.docidentity h1`.

| Viewport | Arrangement | Identity from document start | From product content | From page top | Visible controls before identity | Tab stops before identity | Disclosure target |
|---|---|---|---|---|---|---|---|
| 390 | A | 843px | 1115px | 1448px | 30 | 4 | — |
| 390 | B collapsed | 386px | 657px | 1010px | 2 | 2 | 220×51 |
| 390 | B expanded | 901px | 1173px | 1526px | 31 | 5 | 220×51 |
| 320 | A | 843px | 1115px | 1448px | 30 | 4 | — |
| 320 | B collapsed | 386px | 657px | 1010px | 2 | 2 | 220×51 |
| 320 | B expanded | 901px | 1173px | 1526px | 31 | 5 | 220×51 |
| 1440 | A | 28px | 203px | 331px | 30 | 4 | — |
| 1440 | B | 28px | 203px | 331px | 30 | 4 | — |

- **Identity distance.** B collapsed moves the identity heading 457px closer to
  the start of the document than A (843px to 386px), 54% of an 844px phone
  screen. B expanded is 58px lower than A because the disclosure adds its own
  row.
- **Visible controls.** A places 30 visible controls before the identity: the
  portrait surface, the history button, 16 animal choices and 12 tint choices.
  B collapsed places 2: the portrait surface and the disclosure.
- **Tab order.** A reaches the identity after four tab stops: portrait, history,
  animal, tint. B collapsed after two: portrait, disclosure. B expanded puts
  history, animal and tint after the disclosure, so five stops precede the
  identity, but only after the reader asked for them.
- **Touch floor.** The portrait surface is 220×275 and the disclosure is 220×51
  at both phone widths. The history button is 44×44 in A and in B expanded. All
  meet the 44px floor; the floor does not separate the options.
- **Overflow.** `document.documentElement.scrollWidth` equals the viewport at
  320 and 390 in all three states. No horizontal overflow.
- **Desktop.** A and B have identical geometry and tab order; the disclosure is
  not visible. The arrangement is phone-only by construction.

## Recommendation

**B, the explicit disclosure, on phones; A retained on desktop.**

The measurement that justifies it is the identity distance and the control
count: B collapsed halves the distance to the identity (843px to 386px) and
removes 28 visible controls from the path before it, while the portrait stays
visible and uploadable and both options meet the 44px touch floor. On a 844px
phone, A puts the identity 1.7 screens from the page top and B collapsed 1.2
screens; the 457px difference is the cost of showing every appearance control
first.

What B costs:

- Appearance editing needs one extra tap. The controls are not visible until
  the reader opens `Aspetto`.
- In the open state the identity is 58px lower than in A and five tab stops
  precede it, because the disclosure row is added.
- The editor's live save/error status currently lives inside the choices panel.
  T25 must keep that `role="status"` reachable when the panel is collapsed, or
  move it outside the hidden region.

What A costs:

- The identity is 843px into the document and 1448px from the page top, behind
  30 visible controls and four tab stops, before the reader can read the name.
- The first phone screen after the document start is entirely appearance
  controls.

The recommendation is not the decision. The coordinator records the accepted
option; this study does not declare it.

## Decision (pending)

The coordinator owns the selection. On acceptance, record here:

- the accepted arrangement (A or B) and the rejected one;
- the accepted reading and control order on phones;
- the accepted interaction for opening and closing the controls;
- the T25 scope below that applies.

### T25 scope if A is retained

A retained is an explicit no-change outcome. No production composition changes.
T25 records the retention, keeps the current always-visible controls, the T32
touch floor, the portrait upload and the read-only/locked branch unchanged, and
adds no disclosure. The current captures are the reference.

### T25 scope if B is selected

- `src/frontend/components/editorial/ImageEditor.jinja`: add the phone
  disclosure trigger and an id/`aria-controls` target for the history row and
  the choices. Keep the same forms, `data-upload-url`, `data-autosave-url`,
  `data-version`, symbol/tint options, dialogs and read-only branch.
- `src/frontend/components/editorial/ImageEditor.css`: phone-only collapsed and
  expanded states using the existing `document-column` container query; desktop
  unchanged. Reuse the existing button skin rather than a new control.
- `src/frontend/components/editorial/ImageEditor.js`: toggle `aria-expanded`
  and the hidden state, preserve focus on open and close, and keep the existing
  autosave, upload, history and confirmation handlers. No new save path.
- `src/frontend/components/editorial/Document.css` or its callers only if the
  trigger cannot sit inside the existing portrait column. Prefer no caller
  change.
- Keep the live save/error status outside the collapsed region, or provide an
  equivalent announcement.
- Tests: `tests/frontend/test_image_editor_component.py` for the collapsed and
  expanded contract, the 44px floor, focus order and 320/390 overflow;
  `tests/frontend/test_tint_autosave.py`; `tests/e2e/test_image_editor.py` for
  symbol and tint persistence read back through the API after expanding.
- Update `docs/features-implemented/live-image-editor.md`. No API, token,
  permission or read-only policy change.

## Simulation boundary

- The comparison strip says **Prototipo**, that the data is demonstration data,
  that saves are simulated and disabled, that nothing is recorded, and that the
  comparison is not a product setting.
- Every real write control carries `data-prototype-inert="true"` and a title
  saying the save is disabled. The appearance controls keep their real tab order
  so it can be measured; their activation is blocked instead of disabling them.
  Other write controls are disabled or removed from the tab order.
- Form submits, clicks, edit gestures and non-GET htmx requests are blocked. A
  fetch guard rejects any non-GET request that would bypass the block.
- No file is uploaded, no autosave runs and no campaign data is read or written.
  The study never claims a saved state.

## Run and verify

```console
uv run harness test frontend -- tests/frontend/test_appearance_study.py -q
uv run python prototypes/appearance-study/capture.py
uv run python prototypes/appearance-study/capture.py --serve
```

The test proves the raw page and real assets, equal data and DOM across the two
arrangements, the identity-distance and control-count difference, the focus
order, the 44px targets, no overflow at 320 and 390, the desktop no-change, the
labelled comparison, the inert controls and the absence of write requests.
`capture.py` writes the five committed screenshots and `evidence/revisions.json`
with the measurements above.

`--serve` prints an ephemeral URL and keeps the component server running so the
owner can open the page, switch A/B and open the disclosure. Ctrl+C stops only
that server. This mode writes no evidence and does not start or read the
application, its database or the work/showcase environments.

## Evidence

| Viewport | A | B collapsed | B expanded |
|---|---|---|---|
| Desktop 1440×1000 | [`evidence/desktop-a.png`](evidence/desktop-a.png) | [`evidence/desktop-b.png`](evidence/desktop-b.png) | — |
| Phone 390×844 | [`evidence/phone-a.png`](evidence/phone-a.png) | [`evidence/phone-b.png`](evidence/phone-b.png) | [`evidence/phone-b-open.png`](evidence/phone-b-open.png) |

`evidence/revisions.json` records the base commit, the blob hashes of the real
components the page renders, the fixture identifiers, the capture viewports and
the measurements for every state. The captures describe that revision; the
components are live and a later change moves them, so these images are not a
frozen reference.

The full-page captures neutralise the sticky topbar's paint position only while
the screenshot is taken. Without that, Playwright paints the sticky topbar over
the document at the last scroll tile, which is a capture artifact rather than a
layout result. The measurements are taken before that style is applied.

## What this revision shows

Compared with the 390px review captures and
`prototypes/devin-prototype/`: the same atlas shell, portrait/identity head,
serif prose, related links and appearance controls. The study does not reuse the
prototype's static shell; the shell and the document come from the real catalog.

- At 390px, A reproduces the review: portrait, history, animal, tint, then the
  identity. B collapsed keeps the portrait and replaces the history/animal/tint
  block with one `Aspetto` row, so the identity follows 457px earlier.
- At 1440px, both arrangements are the current document: portrait column beside
  the identity, appearance controls in that column. B changes nothing on
  desktop.

## Limits

- Prototype only. It is not a product setting and does not prove persistence,
  permissions or read-only behavior. Saves are blocked.
- The comparison covers the editable state. The real component renders no
  appearance controls when the document is read-only or locked; the study does
  not change that branch.
- Chromium at 1× device scale, 320/390/1440 viewports. No physical device, no
  iOS Safari, no screen reader and no enlarged-text run.
- The study strip is prototype chrome above the product content. The page-top
  numbers include it; the document-relative numbers do not.
- The disclosure is prototype-local markup with the real button skin. T25 must
  implement it with the supported component vocabulary, not copy this file.
- The fixture is one character with 16 animals and 12 tints. A different choice
  count changes the height and the control count, not the order.

## Files

- `study.py` — typed fixture, catalog render and source revisions.
- `comparison.css` — the prototype strip, the disclosure and option B.
- `comparison.js` — arrangement switching, the disclosure, the inert boundary
  and the live measurement.
- `controls.html` — the labelled comparison strip.
- `capture.py` — desktop/phone captures, measurements and the interactive
  `--serve` entry point on the ephemeral server.
- `evidence/` — committed screenshots and `revisions.json`.
