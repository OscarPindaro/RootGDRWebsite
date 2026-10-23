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
controls. Switching changes `data-study-appearance` on `<body>` and the
component's `data-appearance-expanded` state. The product now ships the phone
disclosure, so the two options are not symmetric:

- **A deliberately reproduces the pre-disclosure arrangement.** Prototype CSS
  overrides the component's collapsed state: it shows the history row and both
  choice grids, restores the editor gap, the choices rows and the status height
  the component tightens when collapsed, and hides the product disclosure. A
  does not depend on the product default; the test sets the component back to
  `data-appearance-expanded="false"` and the controls stay visible.
- **B drives the product's own disclosure.** The rendered `common.Button` with
  `data-image-disclosure`, `aria-expanded` and `aria-controls` is the trigger;
  the component's `data-appearance-expanded` attribute and its own CSS and
  script drive the collapsed and expanded states. The prototype inserts its
  own fallback button only when a rendered component has no product disclosure.
  On this baseline it does, so no fallback is inserted.

| | A · Always visible (reproduced) | B · Product disclosure |
|---|---|---|
| Portrait | Visible, 220×275 at 390px | Visible, 220×275 at 390px |
| Image history | Visible under the portrait | Inside the product disclosure |
| Animal and tint | Visible under the history | Inside the product disclosure |
| Disclosure target | Hidden by prototype CSS | Product button, 220×51 |
| Identity heading | After all appearance controls | After portrait and disclosure |
| Desktop | Unchanged | Unchanged; the disclosure is phone-only |

Option B applies only where the corrected document head stacks the portrait
above the identity (`@container document-column (max-width: 34.5rem)`). At
desktop the head is two columns, the disclosure is not rendered visibly, and the
appearance controls stay in the portrait column exactly as A.

The disclosure sits between the portrait and the controls it reveals. Opening
and closing it changes no form, URL, version or selection.

## Measurements

Taken on the committed captures at 390×844 and 320×844, Chromium, 1× device
scale. "Document start" is the top of `.document`, below the unchanged docbar;
"product content" is the top of `#main`; "page top" includes the prototype strip.
The identity is the `.docidentity h1`.

| Viewport | Arrangement | Identity from document start | From product content | From page top | Visible controls before identity | Tab stops before identity | Disclosure target |
|---|---|---|---|---|---|---|---|
| 390 | A | 843px | 1115px | 1448px | 30 | 4 | — |
| 390 | B collapsed | 394px | 665px | 1018px | 2 | 2 | 220×51 |
| 390 | B expanded | 901px | 1173px | 1526px | 31 | 5 | 220×51 |
| 320 | A | 843px | 1115px | 1448px | 30 | 4 | — |
| 320 | B collapsed | 394px | 665px | 1018px | 2 | 2 | 220×51 |
| 320 | B expanded | 901px | 1173px | 1526px | 31 | 5 | 220×51 |
| 1440 | A | 28px | 203px | 331px | 30 | 4 | — |
| 1440 | B | 28px | 203px | 331px | 30 | 4 | — |

- **Identity distance.** B collapsed moves the identity heading 449px closer to
  the start of the document than A (843px to 394px), 53% of an 844px phone
  screen. B expanded is 58px lower than A because the disclosure adds its own
  row.
- **Visible controls.** A places 30 visible controls before the identity: the
  portrait surface, the history button, 16 animal choices and 12 tint choices.
  B collapsed places 2: the portrait surface and the product disclosure.
- **Tab order.** A reaches the identity after four tab stops: portrait, history,
  animal, tint. B collapsed after two: portrait, disclosure. B expanded puts
  history, animal and tint after the disclosure, so five stops precede the
  identity, but only after the reader asked for them.
- **Touch floor.** The portrait surface is 220×275 and the product disclosure is
  220×51 at both phone widths. The history button is 44×44 in A and in B
  expanded. All meet the 44px floor; the floor does not separate the options.
- **Overflow.** `document.documentElement.scrollWidth` equals the viewport at
  320 and 390 in all three states. No horizontal overflow.
- **Desktop.** A and B have identical geometry and tab order; the disclosure is
  not visible. The arrangement is phone-only by construction.

### Pre-implementation baseline

The earlier T24 study, before T25 shipped the disclosure, measured A at 843px,
B collapsed at 386px and B expanded at 901px at 390px. Those are the
pre-implementation baseline, not this one. A and the expanded state still
measure the same; the product's collapsed state adds its own 8px gap, so B
collapsed is now 394px and the old 386px figure no longer describes the current
components.

## Recommendation and recorded decision

The study recommended **B, the explicit disclosure, on phones; A retained on
desktop**. The coordinator recorded that choice and T25 implemented it. This
maintenance fix does not re-decide it: it keeps A as a deliberate reproduction
for comparison and drives B through the product's own disclosure.

The measurement that justified B is the identity distance and the control
count: B collapsed moves the identity 449px closer (843px to 394px) and removes
28 visible controls from the path before it, while the portrait stays visible
and uploadable and both options meet the 44px touch floor. On a 844px phone, A
puts the identity 1.7 screens from the page top and B collapsed 1.2 screens; the
449px difference is the cost of showing every appearance control first.

What B costs:

- Appearance editing needs one extra tap. The controls are not visible until
  the reader opens `Aspetto`.
- In the open state the identity is 58px lower than in A and five tab stops
  precede it, because the disclosure row is added.
- T25 keeps the live save/error status in flow when the panel is collapsed, so
  a failed save is not hidden. That was the main risk in the earlier record and
  it is handled in the product.

What A costs:

- The identity is 843px into the document and 1448px from the page top, behind
  30 visible controls and four tab stops, before the reader can read the name.
- The first phone screen after the document start is entirely appearance
  controls.

### Recorded decision

- **Accepted:** B on phones; A retained on desktop.
- **Rejected:** A as the phone default.
- **Reading and control order on phones:** portrait, `Aspetto`, identity.
  Opening the disclosure reveals image history, animal and tint before the
  identity.
- **Interaction:** the product button toggles `aria-expanded` and the
  component's `data-appearance-expanded`; closing with focus inside returns it
  to the trigger; no form, URL, version or selection changes.
- **T25 implementation:** the product now ships the disclosure in
  `ImageEditor.jinja`, `ImageEditor.css` and `ImageEditor.js`, with component
  and E2E coverage and the `live-image-editor` manual update. The study's A is
  prototype-only and does not exist as a product mode.

## Simulation boundary

- The comparison strip says **Prototipo**, that the data is demonstration data,
  that saves are simulated and disabled, that nothing is recorded, and that the
  comparison is not a product setting.
- Option B uses the product's own disclosure button and state. The prototype
  inserts its own fallback button only when the rendered component has no
  `[data-image-disclosure]`; on this baseline it does, so no fallback is
  inserted.
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
arrangements, A's explicit override of the component collapsed state, B's use
of the product disclosure, the identity-distance and control-count difference,
the focus order, the 44px targets, no overflow at 320 and 390, the desktop
no-change, the labelled comparison, the inert controls and the absence of write
requests. `capture.py` writes the five committed screenshots and
`evidence/revisions.json` with the measurements above.

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

- At 390px, A deliberately reproduces the pre-disclosure review: portrait,
  history, animal, tint, then the identity. B is the product's shipped
  arrangement: it keeps the portrait and replaces the history/animal/tint block
  with the product's `Aspetto` row, so the identity follows 449px earlier.
- At 1440px, both arrangements are the current document: portrait column beside
  the identity, appearance controls in that column. B changes nothing on
  desktop.

## Limits

- Prototype only. It is not a product setting and does not prove persistence,
  permissions or read-only behavior. Saves are blocked.
- Option A is a prototype-only reproduction of the pre-T25 arrangement. The
  product ships B on phones; A is not a product mode.
- The comparison covers the editable state. The real component renders no
  appearance controls when the document is read-only or locked; the study does
  not change that branch.
- Chromium at 1× device scale, 320/390/1440 viewports. No physical device, no
  iOS Safari, no screen reader and no enlarged-text run.
- The study strip is prototype chrome above the product content. The page-top
  numbers include it; the document-relative numbers do not.
- The fallback disclosure is prototype-local markup with the real button skin.
  On this baseline the product button is used, so the fallback is not measured.
- The fixture is one character with 16 animals and 12 tints. A different choice
  count changes the height and the control count, not the order.

## Files

- `study.py` — typed fixture, catalog render and source revisions.
- `comparison.css` — the prototype strip, A's explicit override and the
  fallback disclosure.
- `comparison.js` — arrangement switching, the product disclosure state, the
  fallback, the inert boundary and the live measurement.
- `controls.html` — the labelled comparison strip.
- `capture.py` — desktop/phone captures, measurements and the interactive
  `--serve` entry point on the ephemeral server.
- `evidence/` — committed screenshots and `revisions.json`.
