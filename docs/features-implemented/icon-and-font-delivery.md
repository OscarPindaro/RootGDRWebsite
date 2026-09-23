# Icon and font delivery

Icons render on the server from a pinned Lucide registry and the fonts are
self-hosted, so a reading page downloads no icon runtime, an htmx swap needs no
icon pass, and typography does not depend on an external network.

## What it does

- `common.Icon` writes a complete inline `<svg>`; nothing scans the DOM for
  placeholders and nothing re-runs after an htmx swap.
- A size is a class reading one step of the `--icon-*` scale, never a
  per-instance `style` attribute.
- An icon name or size that is not in the registry raises, and a test fails when
  a component uses a name the registry does not have.
- Newsreader and IBM Plex are served from `/static/fonts`; only the latin subset
  is committed, and only the two regular faces are preloaded.
- The baseline payload (CSS, shell JavaScript, icons, fonts, the lazy editor) is
  measured and enforced.

## How it is built

### The registry instead of a runtime or a sprite

The application used to ship `lucide.min.js` (417 KB) plus `lucide-init.js`, and
`lucide.createIcons()` replaced every `<i data-lucide>` in the browser — once on
load, again after each swap. `common.Icon` now renders the `<svg>` itself from
`src/backend/icons.py`, a generated dict of Lucide icon bodies. The project
already renders product semantics on the server this way (`backend/content/marks.py`
for role marks); the UI icons simply joined it. Role marks stay separate: they
are product semantics with a shape equivalent, not Lucide chrome.

A committed sprite with `<use>` was the alternative. It was rejected: an external
`<use href="/static/icons.svg#plus">` renders nothing when the symbol is missing
— the silent failure this ticket exists to remove — and it needs a request and a
second file for a payload that is already small inline (all 36 icons once cost
11.8 KB raw, 2.0 KB gzipped; a page uses a fraction of that).

### Reproducing the registry

`tools/build_icons.mjs` imports the pinned `lucide` devDependency, serialises the
listed icons and writes `src/backend/icons.py`. `package.json` pins the exact
version (`"lucide": "1.31.0"`, no range), the generated header names it, and
`tests/unit/test_icons.py` fails if the pin floats. The script runs on demand
(`npm run icons`), never during a build, so no floating `latest` asset can leak
in. The ISC licence is committed as `src/backend/icons.LICENSE`.

The icon inventory (the union of every `icon=` / `confirm_icon=` / `<common.Icon
name=>` in `src/frontend/components` and `src/backend`) is the generator's
`NAMES` list and is asserted equal to what the source uses, in both directions —
a new name fails until it is generated, and an unused entry fails as dead weight:

```
arrow-right  book-open  calendar  check  chevron-down  chevron-up  circle-dot
download  file-text  grid-2x2  history  home  list  lock  lock-open  log-out
mail  map  map-pin  map-pin-off  menu  palette  panel-left-close  pencil  plus
save  settings  shield  star  trash-2  undo-2  upload  user  user-plus  users  x
```

### Sizes

`common.Icon` keeps its pixel argument (`size=24`, `:size="icon_sizes[size]"`),
so no caller changed, and `common.Button` keeps its xs…xl icon map verbatim. The
pixel value is turned into a class inside the component (`icon_class`), and
`common/Icon.css` maps each class to a token in the new `--icon-*` scale in
`main.css`. `Button.css`'s `.btn-icon svg` is more specific and still wins, so
button icon geometry is unchanged.

### Fonts

`main.css` declares five `@font-face` rules with `font-display: swap`, all
pointing at `/static/fonts`:

| File | Family | Axes / weight | Raw |
|---|---|---|---|
| `newsreader-latin-var.woff2` | Newsreader | variable opsz 6–72, wght 200–800 | 132.0 KB |
| `newsreader-latin-var-italic.woff2` | Newsreader | variable opsz 6–72, wght 200–800 | 146.9 KB |
| `ibm-plex-sans-latin-var.woff2` | IBM Plex Sans | variable wght 100–700 | 45.7 KB |
| `ibm-plex-mono-latin-400.woff2` | IBM Plex Mono | 400 | 14.7 KB |
| `ibm-plex-mono-latin-500.woff2` | IBM Plex Mono | 500 | 14.9 KB |

Newsreader keeps its optical-size axis. Dropping it to save 156 KB changed how
every heading renders (about 7 % of the desktop pixels against the previous
build), so the axis is part of the typography, not a payload detail.

The committed files are the **hinted** variant Google serves to desktop user
agents. Google serves an *unhinted* variant to Android user agents, which is why
the same page used to render slightly differently on a phone; self-hosting one
file makes the rendering device-independent. The cost is a small metric shift on
a phone viewport (0.06 points of the prototype pixel diff), where the unhinted
variant used to win — a deliberate trade for determinism.

`layout/BlankPage.jinja` preloads the two regular faces (Newsreader and IBM Plex
Sans) and nothing else. The documented fallback stacks in `main.css`
(`--serif`/`--sans`/`--mono`) are unchanged, and each face declares the latin
`unicode-range`, so a character outside the subset falls back instead of
rendering a blank box. The licences ship beside the files
(`OFL-Newsreader.txt`, `OFL-IBM-Plex.txt`).

### Budgets

Measured by `tests/unit/test_payload_budget.py` (raw and gzip, threshold = value
plus about a third of headroom). The editor is budgeted separately because it
must stay off reading pages.

| Asset | Raw | Gzip | Raw limit | Gzip limit |
|---|---|---|---|---|
| Base CSS (`main.css`) | 45,565 | 11,990 | 60,000 | 16,000 |
| Shell JavaScript (htmx, json-enc, feedback, format-times) | 57,935 | 18,828 | 75,000 | 25,000 |
| Icon assets (the registry's inline markup, one of each) | 11,827 | 2,004 | 16,000 | 4,000 |
| Fonts (self-hosted latin subsets) | 354,180 | 353,965 | 420,000 | 420,000 |
| Lazy editor (`editor.js`) | 557,838 | 191,823 | 620,000 | 210,000 |

For reference, the removed `lucide.min.js` was 417,272 raw / 97,605 gzip on every
page. The font files were already being downloaded from the font host before, so
the baseline loses the icon runtime and keeps the typography it had. The base CSS
figure is F20's measurement; F22 cut `main.css` to 18,154 raw / 5,955 gzip by
moving every component rule out (see [final-consolidation.md](final-consolidation.md)).
The thresholds are unchanged.

### Caching and fingerprinting

`server.py` mounts `/static` and `/static/components` with Starlette's
`StaticFiles`. The response carries `ETag` and `Last-Modified` and honours
conditional requests (a re-request returns `304`), but there is **no
`Cache-Control`, no fingerprinting and no reverse proxy** in front (the
deployment is a single uvicorn container, `Dockerfile`). So assets are
revalidated on every navigation rather than cached immutable — safe, never
stale, at the cost of a conditional request.

No asset pipeline was added. Fingerprinting would mean rewriting every asset URL
(including JinjaX's `render_assets()`), which is a deployment concern, not an
icon one; the current ETag revalidation already avoids re-downloading unchanged
bytes, and the asset set is small (one stylesheet, four scripts, five fonts).
This is a recorded exception: immutable caching is not available today.

## Used by

Every page: `common.Icon` is composed by `Button`, `ButtonGroup`, `IconButton`,
`MenuItem`, `MenuTrigger`, `EmptyState`, `Dialog`, `ConfirmDialog`, `Topbar`,
`UserMenu`, the docbar and the image editor.

## Limits

- Only the latin subset is committed; a page in a non-latin script falls back to
  the stack's system font. Adding a subset means adding a `@font-face` and the
  file.
- IBM Plex Mono ships 400 and 500 only, matching what the stylesheets ask for; a
  bolder mono is synthesised.
- The icon registry covers UI chrome. Role marks remain in
  `backend/content/marks.py` and are deliberately not part of it.
- Assets are revalidated, not cached immutable (see above).
