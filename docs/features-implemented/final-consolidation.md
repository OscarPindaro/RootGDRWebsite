# Final consolidation (F22)

The last ticket of the frontend mega-plan removes the transitional system. Every
selector an earlier ticket migrated leaves `main.css` for the stylesheet that
owns it, the components nobody calls are deleted, and two static tests hold the
line: one root has one owner, and a retired name does not come back.

## What changed

### `main.css` reduced to the global layer

`main.css` now holds only what the guide calls global: the identity and alias
tokens, the reset, base typography (`.display`, `.eyebrow`, `.lede`, `.mono`,
`.muted`), the reading measure (`.container`), prose, `.hint`, the utility atoms
(`.spread`, `.hr`, `.sr-only`), the accent-rule atom (`.rule-accent`) with its
`html[data-accent]` preference rules, the `html[data-accent]` prose-link rule,
and the M3 alias token block. It no longer styles a single component root.

The classification, rule group by rule group:

| Rule group (old `main.css`) | New owner | Action |
|---|---|---|
| `@font-face`; `:root` identity tokens; reset; `.display`/`.eyebrow`/`.lede`/`.mono`/`.muted`; `.container`; `.prose`; `.hint`; `.spread`/`.hr`/`.sr-only`; `html[data-accent]` rules; M3 alias `:root`; `h1,h2,h3` | `main.css` | kept (global) |
| `.rule-accent` | `main.css` | kept (identity atom, shared by Masthead and Login) |
| `.masthead*` | `editorial/Masthead.css` | moved |
| `.crumbs*` | `editorial/Crumbs.css` | moved |
| `.section`, `.section__head*` | `editorial/SectionHead.css` | moved |
| `.cover*` | `editorial/Cover.css` | moved |
| `.quick*` | `editorial/Quick.css` | moved |
| `.feature*` | `pages/places/PlaceList.css` | moved |
| `.timeline`, `.tl*` | `editorial/Timeline.css` | moved |
| `.toc*` | `pages/pages/PageDetail.css` | moved |
| `.pager*` | `pages/sessions/SessionDetail.css` | moved |
| `.mark*` | `common/Mark.css` | moved (`common.Shape` declares it too) |
| `.plogo*` | `editorial/Plogo.css` | moved |
| `.face*` | `editorial/Face.css` | moved |
| `.links*` | `editorial/Links.css` | moved |
| `.wherenow*` | `pages/worlds/WorldOverview.css` | moved |
| `.document__*`, `[data-doc-block].document-block--active` | `editorial/Document.css` | moved (shared by the six detail pages) |
| `.document__face--editor*` | `editorial/Document.css` | moved from `ImageEditor.css`, so `document` has one owner |
| `.docedit` (`position: relative`) | `editorial/DocEdit.css` | moved |
| `.autosave-recovery .btn` (phone) | `editorial/DocEdit.css` | moved |
| `.stat*` | — | deleted (component removed) |
| `.callout*`, `.dateline*`, `.hero*`, `.md-panel`, `.md-empty`, `.media-fallback` | — | deleted (no caller) |
| `.docfield*`, `.document__rule/__controls/__meta/__meta-label`, `.filefield*` | — | deleted (no caller) |
| `.form`, `.swatch*`, `.swatches*`, `.shapebtn*`, `.emojigrid`, `.emojibtn`, `.preview*` | — | deleted (old form-editor leftovers, no caller) |
| `.filterbar*`, `.kindnote*`, `.palette-strip*`, `html[data-views]`, `html[data-editor]`, `.only-*` | — | deleted (prototype view/editor toggles, superseded) |
| `.tabs`, `.tab` | — | deleted (`common/Tabs` owns `.tabs`; the prototype strip is gone) |
| `.grid--two` | — | deleted (no caller; `common.Grid` owns `.grid`) |
| `.docedit__view/__input/__caret/__caretline/__mirror` | — | deleted (textarea editor replaced by CodeMirror) |
| `.face--editable`, `.face__hint`, `.face__remove`, `.face--lg`, `.mark--lg`, `.plogo--sm`, `.cover__counts`, `.eyebrow--ink`, `.eyebrow--paper`, `.toc a.is-current`, `.toc a.with-mark` | — | deleted (no caller) |
| `.prose :where(.prose) .ProseMirror > * + *` | — | deleted (ProseMirror engine is gone; the server-HTML selector stays) |

Two decisions inside that table:

- **`.rule-accent` stays in `main.css`.** It is the accent-rule atom, rendered by
  `editorial.Masthead` and the Login cover and driven by the `data-accent`
  preference, so it is identity, not a component root. The preference is not
  wired yet (nothing writes `data-accent`); `features-request/frontend.md` now
  says so.
- **`.section` moved with `.section__head`.** They share the root `section` and
  every page that renders `<section class="section">` also renders
  `editorial.SectionHead`, so the component owns both.

Raw px and raw hex are not allowed in a component stylesheet, so the moved rules
were converted: px to `rem`, and the five full-tint hover shades to new
`--*-deep` identity tokens (`--vermilion-deep`, `--cobalt-deep`, `--ochre-deep`,
`--forest-deep`, `--plum-deep`). The rendered values are byte-identical.

### Dead components deleted

| Component | Why |
|---|---|
| `Hello.jinja` | no caller anywhere |
| `editorial/Stat.jinja` | no caller; the overview uses `Quick` and `Timeline` |
| `layout/Sidebar.jinja`, `SidebarItem.jinja`, `SidebarSection.jinja`, `Sidebar.css`, `Sidebar.js` | the rail replaced the M3 drawer in F15; F22 removed the dead files and the `.sidebar-collapsed` rules `UserMenu.css` still carried |
| the `palette` icon in the registry | its only caller was `SidebarItem`; `tools/build_icons.mjs` and `src/backend/icons.py` dropped it |

`tests/unit/jinja/test_jinja_filters.py::test_the_showcase_link_is_development_only`
was retargeted from `layout.Sidebar` to `layout.Page`, which resolves the same
`global_nav` through the catalog's `env`. The assertion is unchanged.

### The retired names cannot come back

`tests/unit/jinja/test_legacy_selectors.py` scans `src/frontend/components/**`
and `src/frontend/js/**` (templates, scripts and stylesheets) and fails on a name
an earlier ticket retired. It strips block comments first, so a file may still
name what it replaced. The list, with its origin:

| Pattern | Retired by |
|---|---|
| `.btn--*` double-dash | F3 |
| `.pill--*` double-dash | F3 |
| `.card--*` double-dash, `.card__monogram`, `.card__faction` | F14 |
| `.docpage`, `.article` | F2/F14 |
| `.grid--quick`, `.grid--two`, `.grid--cards`, `.stack`, `.row-inline` | F5/F21 |
| `.field__bar`, `.field__hint`, `.field-label`, generic `.input`/`.textarea`/`.select` | F4 |
| `.cover--new` | F13 |
| `.rowlist` | F14 |
| `data-lucide`, `createIcons`, `lucide.min.js`/`lucide-init` | F20 |
| `sidebar-collapsed` | F16/F22 |
| `location.reload` in a component script | F7/F19 (the autosave conflict recovery in `src/frontend/js` may still reload) |

Each pattern is anchored so it cannot fire on a legitimate neighbour
(`.entity-card--npc` is not `.card--`; `.h-stack` is not `.stack`), and a second
test asserts every pattern still matches a representative retired spelling, so a
pattern that stops being able to fire fails instead of giving false comfort.

### The ownership guard, extended

`tests/unit/jinja/test_component_conventions.py` watches the roots F22 moved in
addition to the F14 set — `cover`, `crumbs`, `docedit`, `document`, `face`,
`links`, `mark`, `masthead`, `plogo`, `quick`, `section`, `timeline` — and
`MIGRATION_ALLOWLIST` stays empty. To keep `mark` one-owner, the two
`… .mark--shapes` rules became `…[data-mark-style="shapes"]` (the attribute the
server and `Mark.js` already set).

### The showcase

`pages/showcase/Showcase.jinja` now describes the final system:

- the intro says what the system is and where the M3 provenance lives
  (`src/frontend/design-tokens/material3/`), instead of "every value reads from
  tokens";
- **Buttons**: the "M3 Expressive sizes, shapes, icon layouts, toggle state"
  copy is gone. The section leads with purpose and production variants
  (`primary`, `secondary`, `danger`, `text` at `sm`/`md`), then states, icon
  layouts and the toggle, and finally the M3-inventory skins (`filled`, `tonal`,
  `outlined`, `elevated`) with a note that no production page calls them. The
  unused giant specimens (`lg` 96px, `xl` 136px) are removed;
- **Typography** explains the alias scale versus the atlas classes, **Icons**
  explains server rendering and how to add one; both previously had no note.

## Compare numbers

`uv run harness compare <path> --base-url http://localhost:8002`, clean before
(`git stash`) and after, on the seeded showcase database. Every mapped page is
identical; the 0.01% on the worlds list is the "Aggiornato" time text, not a
layout change.

| Page | Desktop before → after | Phone before → after |
|---|---|---|
| Worlds list | 27.77% → 27.78% | 19.69% → 19.69% |
| World overview | 17.76% → 17.76% | 17.56% → 17.56% |
| Characters list | 47.32% → 47.32% | 55.72% → 55.72% |
| Character detail | 20.22% → 20.22% | 30.58% → 30.58% |
| NPCs list | 46.40% → 46.40% | 53.68% → 53.68% |
| Places atlas | 30.40% → 30.40% | 40.05% → 40.05% |
| Place detail | 25.87% → 25.87% | 40.61% → 40.61% |
| Sessions ledger | 9.47% → 9.47% | 15.46% → 15.46% |
| Session detail | 23.43% → 23.43% | 23.26% → 23.26% |
| Stories list | 31.54% → 31.54% | 33.65% → 33.65% |
| Story detail | 17.75% → 17.75% | 29.45% → 29.45% |
| Pages list | 8.02% → 8.02% | 13.85% → 13.85% |
| Page detail | 16.72% → 16.72% | 20.96% → 20.96% |

The absolute percentages are the data and font-rendering difference against the
prototype; the signal is that none of them moved.

## Payload delta

`main.css` (the "base CSS" budget in `tests/unit/test_payload_budget.py`):

| | Raw | Gzip |
|---|---|---|
| Before | 45,771 B | 12,067 B |
| After | 18,154 B | 5,955 B |
| Δ | −27,617 B (−60%) | −6,112 B (−51%) |

The icon registry lost one icon (`palette`), a few hundred bytes of inline
markup. Both budgets pass with the extra headroom; no threshold was changed.

## How to reproduce

```bash
uv run python -m pre_commits.jinjax_css_dependencies --check
uv run python -m pre_commits.design_tokens
uv run harness material check
uv run harness test unit
uv run harness test frontend
uv run harness env up --mode local && uv run harness test integration
uv run harness env up --mode docker && uv run harness test e2e --fresh
uv run harness compare /worlds/<id> --base-url http://localhost:8002
```

## Limits

- The accent-treatment preference is still not wired (no writer sets
  `data-accent`); the CSS waits in `main.css`.
- The legacy-selector list is the names the tickets actually retired, not every
  name the prototype used. A prototype class the application never adopted is
  not watched.
- The ownership guard watches roots, not kebab-case variants that shadow one
  (`.card-elevated` beside `.entity-card--npc`); that limit is unchanged from
  `css-ownership.md`.
