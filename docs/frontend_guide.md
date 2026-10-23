# Frontend guide — how to build a screen

The frontend is server-rendered: [JinjaX](https://jinjax.scaletti.dev/)
components and [htmx](https://htmx.org/), no client-side framework. This file is
the practical contract for anyone — human or model — adding, changing or
reviewing frontend code. It states who owns what, which options are public, and
what each check actually proves.

The thematic manuals own the detail; this guide links to them instead of
copying them:

- [jinjax.md](jinjax.md) — JinjaX mechanics and this application's wiring.
- [features-implemented/css-ownership.md](features-implemented/css-ownership.md)
  — one owner per selector, the asset seam, and the host/fragment evidence.
- [features-implemented/component-vocabulary.md](features-implemented/component-vocabulary.md)
  — the accepted public options, their consumers and the token policy.
- [features-implemented/document-layout.md](features-implemented/document-layout.md)
  — the six detail pages' grid and reflow contract.
- [features-implemented/shell.md](features-implemented/shell.md) — rail, topbar,
  drawer and identity.
- [features-implemented/dialog-pattern.md](features-implemented/dialog-pattern.md)
  — the shared dialog, focus and error contract.
- [features-implemented/in-place-editing.md](features-implemented/in-place-editing.md)
  — autosave, versions, drafts, the editor host boundary.
- [features-implemented/component-tests.md](features-implemented/component-tests.md)
  — the browser test runner.
- [design_guide.md](design_guide.md) — the portable design process.
- [features-request/frontend.md](features-request/frontend.md) — the settled
  visual decisions.

## 1. Where things live

| Path | Holds | Knows about |
|---|---|---|
| `src/frontend/components/common/` | Reusable primitives: Button, Card, Field, Menu, Dialog, ConfirmDialog, Pill, Table, Avatar, Alert, Divider, Tooltip, ChoiceGrid, ButtonGroup, Grid, VStack, HStack, Icon, IconButton, Mark, Shape, MediaFrame, EmptyState, Switch, Tabs, SaveIndicator, Combobox, RequestFallback | nothing domain-specific |
| `src/frontend/components/editorial/` | The product's vocabulary and its atlas identity: Masthead, Crumbs, Cover, Quick, Timeline, Plogo, Face, EntityCard, StoryCard, StoryBand, Ledger, Row, RowList, CollectionCreate, Docbar, DocIdentity, DocEdit, DocSummary, Links, Metadata, ImageEditor, SectionHead | worlds, characters, sessions, the printed-atlas look |
| `src/frontend/components/layout/` | Page shells: BlankPage, Page, Rail, Topbar, UserMenu | the shell, not the content |
| `src/frontend/components/pages/` | Full pages composed from the three above, one folder per module | the domain |
| `src/frontend/static/css/main.css` | Identity and alias tokens, reset, base typography, prose, and genuinely global document defaults | — |
| `src/frontend/static/js/` | Built application bundles (`editor.js`, `report.js`, `drawings.js`) and the small runtime scripts (`feedback.js`, `format-times.js`, `htmx`, `json-enc`) | — |
| `src/frontend/js/` | Sources for the three bundles. Rebuild with `npm run build:editor`, `build:report` or `build:drawings` and commit the output | — |
| `src/frontend/static/fonts/` | Self-hosted Newsreader and IBM Plex latin subsets and their licences | — |
| `src/backend/icons.py` | Generated Lucide registry; `common.Icon` renders from it | — |
| `src/frontend/design-tokens/material3/` | Provenance for every value adopted from Material 3 | — |
| `tests/frontend/` | Component tests, one file per component or surface | — |
| `tests/unit/jinja/` | Template conventions, selector ownership, retired names, option rejection | — |

**The rule for choosing a folder:** if the component would still make sense in
an unrelated project, it belongs in `common/`; if it speaks about worlds,
volumes, faces or the atlas, it belongs in `editorial/`.

## 2. Styling: tokens, ownership and the public vocabulary

### Two token layers, one source

`main.css` has the identity tokens at the top and an alias layer below it.

- **Identity tokens** — `--paper`, `--surface`, `--ink`, `--muted`, `--line`,
  `--rail*`, the twelve tints `--p1 … --p12`, the semantic `--ok`/`--warn`/
  `--danger`, the type stacks `--serif`/`--sans`/`--mono`, `--radius`, `--rule`,
  `--rule-ink`, and the layout measures.
- **Alias layer** — `--clr-*`, `--sp-*`, `--radius-*`, `--shadow-*`,
  `--status-*`, `--role-*`, `--cat-*`, `--button-*`, `--grid-min-*`,
  `--media-ratio-*`, `--switch-*`. These point back at the identity tokens.

Rules:

1. **Component CSS reads tokens for the palette and shared scales.** A hex
   colour literal fails the `design-tokens` hook (`E920`,
   `src/pre_commits/design_tokens/hook.py`). A raw `px` measurement fails unless
   the declaration is a border, outline, shadow or text-shadow, where the pixel
   is the line itself. Private geometry uses a local `rem`/`clamp` value
   (see "Private geometry" below).
2. **A component that needs a new shared value adds a token**, it does not
   inline the number. Name the token by role (`--grid-min-card`), never by
   value.
3. **Prefer an existing token over a new one.** The spacing scale is
   `--sp-1 … --sp-20`; there is no `--sp-7`.
4. **`main.css` has a restricted role**: identity and alias tokens, the reset,
   base typography, prose, and genuinely global document defaults (`.container`,
   `.display`, `.eyebrow`, `.lede`, `.mono`, `.muted`, `.hint`, `.spread`, `.hr`,
   `.sr-only`, `.rule-accent`, and the `html[data-*]` preference rules). Every
   rule a component owns lives in that component's colocated stylesheet; page
   composition lives beside the page. **New layout CSS does not go there**: use
   `common.Grid`, `common.VStack`, `common.HStack` (§5).

### Selector ownership

Every reusable root selector has **one** owner:

| Layer | Owns | Examples |
|---|---|---|
| `main.css` | identity and alias tokens, reset, base typography, prose, global document defaults | `.prose`, `.container`, `.display`, `.rule-accent` |
| colocated component CSS | structure and states for that component only | `.btn`, `.field`, `.entity-card`, `.dialog`, `.rail`, `.topbar`, `.masthead`, `.face`, `.quick` |
| a shared editorial stylesheet with no component | a structure several components and pages share | `editorial/Collection.css`, `editorial/Document.css`, `editorial/Reference.css` |
| page CSS (`components/pages/**/<Page>.css`) | exceptional page composition, never a reusable primitive | `.login-page`, `.feature`, `.wherenow`, `.pager`, `.toc` |
| `design-tokens/material3/` | provenance for adopted mechanics and dimensions, not a second visual identity | — |

A **root** is the class a selector starts with, stripped of its BEM suffix:
`.entity-card__body` and `.entity-card--npc` both belong to root `entity-card`. A selector whose first
compound carries no class (`.rail .btn`, `html[data-accent] .btn--text`) belongs
to no class root. A domain component that needs its own look takes a domain name
(`entity-card`, `document`, `collection-create`) instead of colliding
with a common primitive.

`tests/unit/jinja/test_component_conventions.py` fails when two stylesheets own
the same root. F14 emptied `MIGRATION_ALLOWLIST`; F22 moved the last editorial
families out of `main.css` into their components and added no exception, so the
list stays empty and `main.css` owns no component root. The guard watches `btn`,
`card`, `collection-meta`, `collection-surface`, `cover`, `crumbs`, `dialog`,
`docedit`, `document`, `entity-card`, `face`, `field`, `icon`, `ledger`, `links`,
`mark`, `masthead`, `pill`, `plogo`, `quick`, `row`, `row-list`, `section`,
`story-band`, `story-card`, `table` and `timeline` — `btn` is Button's root
class, and there is no `.button` selector.

`tests/unit/jinja/test_legacy_selectors.py` is the other half: it fails if a
name an earlier ticket retired (`.btn--*`, `.pill--*`, `.card--npc`, `.docpage`,
`.article`, `.field__bar`, `.grid--quick`, `lucide`, `data-lucide`,
`createIcons`, `location.reload` in a component script, …) comes back in a
component template or script. It strips comments first, so a file may still
name what it replaced.

### Public vocabulary and its enforcement

The public options are finite and recorded in
[features-implemented/component-vocabulary.md](features-implemented/component-vocabulary.md),
with the owner's accepted choices and the tests that check them. In short:

| Component | Argument | Accepted |
|---|---|---|
| `common.Button` | `variant` | `primary`, `secondary`, `text`, `danger` |
| `common.Button` | `size` | `xs`, `sm`, `md`; `lg` and `xl` are design-kit experiments, not product options |
| `common.Button` | `shape` | reserved no-op: the class is emitted and no stylesheet styles it |
| `common.Pill` | `variant` | the 21 status, role and product names listed in the manual |
| `common.Grid` | `columns` | `2`, `3` |
| `common.Grid` | `min` | `card`, `cover`, `story`, `quick` |
| `common.Grid` | `gap` | one of the `--sp-*` steps |
| `common.Grid` | flags | `flush`, `split`, `document` |

An undeclared value **fails the render**. `Button.jinja`, `Pill.jinja` and
`Grid.jinja` call the `component_option` Jinja global in a `{% do %}` after
`{#def #}` and before they build a class:

```jinja
{% do component_option("common.Button", "variant", variant, "primary", "secondary", "text", "danger") %}
```

`_component_option` in `src/backend/jinja.py` raises `ComponentOptionError` with
the component, the argument and the rejected value, then the accepted list:

```text
common.Button: argument 'variant' does not accept 'ghost'; expected one of: primary, secondary, text, danger
```

No markup is produced; the application answers 500 and the server log carries
the message. The check covers exactly the finite arguments above — Button
`variant` and `size` (including `lg`/`xl`), Pill `variant`, Grid `columns`,
`gap` and `min`. Native HTML attributes, `class`, `data-*` and `aria-*` still
pass through `attrs`. The standalone Button `shape` is accepted without a value
check. `ButtonGroup.button_variant` and `ChoiceGrid.columns` are separate
arguments with their own rules.

`tests/unit/jinja/test_component_options.py` renders every documented value and
pins the rejection cases. `tests/frontend/test_component_vocabulary.py` reads
the manual's machine-checked block and keeps the templates, stylesheets, tokens
and design-kit callers on the same list. There is no static value check: an
invalid literal in a branch that never renders is reported only when that
branch renders.

**Private geometry.** A component's own geometry stays in its stylesheet: its
`rem` and `clamp` values, BEM internals, one-off alignments. Examples are the
pill's `0.35rem` gap and `0.15rem` vertical padding, and the text button's
`0.06em` letter spacing. These are not public options and need no token in
`main.css`. A value shared across components, or belonging to the palette or a
shared scale, still belongs in `main.css`.

The token guard's actual rule (`E920`, `src/pre_commits/design_tokens/hook.py`):

- a hex colour literal is a palette violation;
- a `px` length is a violation unless the declaration's property starts with
  `border`, `outline`, `box-shadow` or `text-shadow`;
- `rem`, `em` and `clamp` values pass as private geometry. Rewriting a shared
  `px` value as `rem` does not move it into the token layer: passing the hook is
  not proof of token compliance;
- values inside `url(...)`, `@media` queries and comments are skipped;
- `/* design-tokens: off */` on a line, or in a file's first three lines, skips
  that line or file. The retained opt-outs and their reasons are recorded in
  the vocabulary manual.

`tests/unit/test_design_tokens.py` covers both legitimate private geometry and
genuine violations. A green hook run is not a visual review.

## 3. Anatomy of a component

```
src/frontend/components/common/Switch.jinja
src/frontend/components/common/Switch.css
src/frontend/components/common/Switch.js     # only when it needs behaviour
```

```jinja
{#def label, name, checked=False #}
{% set classes = "switch" ~ (" switch--disabled" if disabled else "") %}
<div {{ attrs.render(class=classes) }}>
  {{ content }}
</div>
```

- **`{#def … #}` must start a line.** JinjaX finds it with a line-anchored
  match; a declaration in the middle of a line is invisible and the component
  ends up with no arguments.
- **A `{% set %}` that reads an argument must come after the `{#def #}` line.**
  Anything before it runs before the arguments are bound and raises
  `UndefinedError` at render time. `{#css … #}` may come first.
- **Declare every argument.** Undeclared props land in `attrs`.
- **The root element carries a class named after the component** plus modifiers
  (`switch`, `switch--disabled`, `tabs__label`).
- **`element` for the tag.** A component that can be a landmark takes an
  `element` argument (`VStack`, `HStack`, `MediaFrame`), so
  `<common.VStack element="aside">` stays an `<aside>`. `as` is not usable: it
  is a Python keyword and JinjaX parses the declaration with Python's parser.
- **Merging caller attributes.** Use `attrs.render(class=…, style=…)`. Writing
  `class="…"` next to `{{ attrs.render() }}` emits a **second** `class`
  attribute; the browser keeps the first and the caller's class is lost. Style
  is replaced, not merged, so read the caller's value yourself:
  `style="--stack-gap: var(--sp-{{ gap }}); {{ attrs.get('style', '') }}"`
- **Forwarding.** To pass caller attributes to a child component use
  `_attrs={{ attrs }}`. Never put `{{ attrs.render() }}` inside a component
  invocation.
- **`{#css … #}` declares the assets the component needs** — its own sibling
  stylesheet, then the CSS of the components it composes. The declaration is
  what the `jinjax-css-dependencies` hook checks and merges; `--check` fails
  naming the component and the asset. It does not put a `<link>` into an htmx
  fragment response: a fragment is markup only and relies on its host having
  declared the sheets (§7).
- **Composition over duplication.** `common.IconButton` is `Tooltip` +
  `Button`; `common.EmptyState` reuses `Icon`. Do not re-implement a control.
- **Values in Jinja.** `size=32` is the **string** `"32"`. Use `size={{ 32 }}`,
  or quote it and convert inside the component.

## 4. Adding, changing, removing

**A new component — checklist**

1. Does something already do this? Check `/components` (the living kit) and
   `common/`. Extend before you add.
2. Create `<Name>.jinja` (+ `.css`, + `.js` when it has behaviour) in the right
   folder, following §3.
3. Add a specimen to `pages/showcase/Showcase.jinja`, with a one-line note
   saying what it is for. Add its CSS to that page's `{#css #}` line.
4. Write `tests/frontend/test_<name>.py` covering the contract, not the
   implementation: the sizes, the states, the keyboard model, the edge cases.
5. If htmx returns the component as a fragment, declare its CSS and JS on the
   host page as well (§7).
6. Run `uv run harness test frontend`.
7. Screenshot desktop and phone (`uv run harness screenshot`) and compare with
   `prototypes/devin-prototype/`.
8. Write `docs/features-implemented/<name>.md` and add it to the index in
   `docs/features-implemented/README.md`.

**Changing an existing component**

1. Read its test file first: it states the contract you are about to change.
2. Change the component, then the test, then the callers. A component with no
   caller and no test is dead code — delete it.
3. If the change touches geometry or interaction, check it against
   `features-request/frontend.md`: **stable geometry** is a decision, not a
   preference.

**Changing CSS or a token**

1. Change the token, not the component, when the value is shared.
2. If the token is inventoried in `design-tokens/material3/`, update the YAML in
   the same commit; `uv run harness material check` and the unit suite both fail
   otherwise.
3. Adding a rule for a reusable root to a second stylesheet fails the ownership
   guard in §2 — give the domain component a domain name instead.
4. Run `uv run harness test frontend` and take a screenshot: a CSS change is
   invisible to every other check.

## 5. Layout ownership

Two layers own layout and they do not overlap: the shell reserves navigation
space, the page owns its content geometry.

**The shell reserves space.** `--rail-w` (276px) is an identity token in
`main.css`. `layout/Page.css` offsets `.main` by it; at `max-width: 900px` the
same file drops the offset and `layout/Rail.css` turns the column into the
drawer. The shell owns that offset and the shared `.container` measure
(`max-width: 1220px` in `main.css`); it sets no page grid and no document width.
A page that needs a different composition changes its own stylesheet. The
drawer's three states are in
[features-implemented/shell.md](features-implemented/shell.md).

**The document page owns its grid and head reflow.** All six content detail
pages compose `<common.Grid document>` and wrap the head in
`.document--sized`; `pages/characters/CharacterDetail.jinja` is the
representative caller. `common.Grid` only emits the `grid-document` class. The
geometry belongs to `editorial/Document.css`:

- `.grid.grid-document` sets
  `minmax(0, 1fr) minmax(0, var(--grid-aside))`, the document gap and
  `container-type: inline-size`; the two classes outrank `.grid` whichever
  stylesheet is collected first.
- `@container (max-width: 53.75rem)` spans both children, so the aside stacks
  under the document instead of squeezing it.
- `.document--sized` registers the named `document-column` inline-size
  container; `@container document-column (max-width: 34.5rem)` moves the
  portrait above the identity.

Both queries measure the width the document is actually given. A viewport
breakpoint cannot express this: above its own breakpoint the shell reserves
276px for the rail, so the same viewport width means two different document
widths. A new detail page copies both the `document` flag and the `--sized`
modifier; without the modifier the named query never matches. The accepted
thresholds, the six-page matrix and the remaining prototype differences are in
[features-implemented/document-layout.md](features-implemented/document-layout.md);
`tests/frontend/test_document_layout.py` asserts them at the boundary widths.

**Primitive variants.** Use the primitives, not classes:

- `<common.Grid columns=N>` fixed columns; `min="card|cover|story|quick"`
  auto-fit with a token minimum; `split` content beside an aside; `gap=N`;
  `flush` for the border-sharing strip; `document` for the detail-page grid.
- `<common.VStack>` / `<common.HStack>` with `gap`, `align`, `justify`, `wrap`
  and `element`.
- A new grid ratio belongs in `Grid.css` as a variant, not in a page as an
  inline `grid-template-columns`.

**When a page may own local composition.** A page may own composition when the
geometry is exceptional to that page and no other page reuses it: that is what
`components/pages/**/<Page>.css` is for. A structure several pages share
belongs in a shared editorial stylesheet with no component
(`editorial/Collection.css`, `editorial/Document.css`,
`editorial/Reference.css`), not copied into each page. A reusable primitive's
variant belongs in the primitive's stylesheet. New layout CSS does not go into
`main.css`, and no second stylesheet may own a watched root (§2).

## 6. Interaction and accessibility

- **Native HTML first.** A real `button`, `input`, `label`, `fieldset` or
  `dialog` before a `div` plus ARIA. `common.Tabs` is a radio group for this
  reason; `common.Switch` is a checkbox with `role="switch"`.
- **Stable geometry.** Shape and width do not change between enabled, hovered,
  pressed and selected states, and pressing never moves a neighbour. Communicate
  state with colour, fill, border and focus ring.
- **Waiting is text and ink, not a spinner.** An htmx request is marked busy by
  `static/js/feedback.js`: the control is `disabled` and `aria-busy` and keeps
  its box, with an ink rule (`is-busy`); a long, genuinely indeterminate job owns
  its own text instead. A failed request a surface does not own shows one
  page-level `common.RequestFallback`; a failed navigation gets
  `pages.errors.ErrorPage`.
- **Motion is functional.** Respect `prefers-reduced-motion`; never use motion
  as the only signal of a selection.
- **Touch targets** are at least `--touch-target` (44px) where a control is used
  on a phone.
- **Focus is always visible**, and independent from hover. The mount, focus and
  dialog return contracts are in §8.
- **A component opened from the dark rail** exposes its surface as local custom
  properties and lets the host override them (see `common/Menu.css`).
- **Labels are not optional.** An icon-only action takes a `label` that reaches
  `aria-label` and the tooltip.
- **Icons render on the server.** `common.Icon` takes a Lucide `name` and a
  pixel `size`, and writes the `<svg>` itself from `src/backend/icons.py`. Its
  size becomes a class reading the `--icon-*` scale, never an inline `style`; a
  name or a size that is not in the registry raises. To add an icon, add the
  name to `tools/build_icons.mjs` and run `npm run icons`. Never reintroduce a
  DOM-scanning icon runtime: an htmx swap must need no icon pass.

## 7. Hosts, assets and swap boundaries

**A full page declares its assets in the head.** `layout/BlankPage.jinja` writes
`main.css` and `catalog.render_assets()`.

**An htmx fragment is markup only.** It carries no `<link>` and no `<script>`;
the host page declares the fragment's stylesheets and scripts. The admin host is
the reference case: `pages/admin/AdminDashboard.jinja` declares
`pages/admin/InviteDialog.css`, `common/Dialog.css` and `common/Dialog.js` in
its `{#css #}`/`{#js #}` lines, while `pages/admin/InviteDialog.jinja` declares
only its own dependencies. Without the host declaration the swapped dialog is
unstyled and never opens. There is no dynamic asset loader: a fragment swapped
into a host that did not declare its sheets renders unstyled.

What the tests prove, and nothing more:

- `tests/frontend/test_asset_delivery.py` separates the claims. An isolated
  mount of a full page and of the fragment asserts that every declared sheet
  was fetched and parsed and that the computed styles the test asks for match;
  the harness shell supplies those assets, so this proves the declarations. A
  raw render of `pages.admin.AdminDashboard` served as the host asserts the same
  sheets are parsed before any swap, injects the real fragment markup, fires
  `htmx:afterSwap`, and asserts the dialog opens and is named, the computed
  styles apply, no stylesheet is added, and a second swap behaves identically.
- `tests/integration/test_admin_views.py` asserts the server side: the host
  declares the dialog's sheets and script, the fragments contain no `<link>` or
  `<script>`, and a repeated duplicate invite returns the same retargeted
  dialog.
- `tests/e2e/test_admin_settings.py` exercises the real request seam, including
  the duplicate-invite `HX-Retarget`.

These tests cover the surfaces they name; they do not prove that every
component's assets are declared. The `jinjax-css-dependencies` hook checks the
declarations, and `tests/unit/jinja/test_component_conventions.py` checks the
class/root seam. The delivery model and its limits are recorded in
[features-implemented/css-ownership.md](features-implemented/css-ownership.md).

**The editor swap boundary.** A dialog is a fresh surface swapped into a
container. A document editor is mounted once per block: the server preview swaps
only the **children** of `[data-doc-render]` and `[data-summary-render]`
(`hx-swap="innerHTML"`), while the host block, the hidden source, the editor
host, the actions row and the `[data-doc-block]` element survive. Replacing a
whole `[data-doc-edit]`, `[data-doc-summary]`, `[data-doc-identity]` or
`[data-doc-metadata]` block — or a `[data-doc-block]` element — with
`outerHTML`, or with a swap of an ancestor that contains it, is **not
supported**: the autosave map is module-level and keyed by URL, `register()`
keeps the first apply callback and root, and the open/close closures live on the
replaced nodes. The observed consequences and the rules for an agent are in
[features-implemented/in-place-editing.md](features-implemented/in-place-editing.md#editor-host-boundary).

**Dialog hosts.** Render the dialog fragment into a container
(`<div id="invite-dialog">`) and let the component handle the swap. Do not drive
opening with an inline `hx-on::after-request`; `common/Dialog.js` opens any
dialog an htmx swap inserts and closes it after a successful request from
inside. Focus, Escape, pending and error behaviour are in
[features-implemented/dialog-pattern.md](features-implemented/dialog-pattern.md).

## 8. Mount, focus, error and persistence

**Mount guards.** `mountAll(root)` in `src/frontend/js/editor/index.js` runs once
on load and again on `htmx:afterSwap`, scoped to `event.target`. Each mount
checks a guard attribute first — `data-doc-ready`, `data-summary-ready`,
`data-identity-ready`, `data-metadata-ready` — and returns when it is set, so a
re-scan after a preview does not create a second editor or duplicate the block's
listeners. The guard lives on the block, so it survives a child-only swap and is
lost when the block is replaced (§7).

**Focus.** The document navigator orders `[data-doc-block]` stops by the product
sequence, not DOM nesting; opening a block focuses its editor, closing restores
the block and the caret position. A dialog remembers its opener and returns
focus on cancel and completion; when the request swaps the opener away, the
action declares `data-dialog-return="<id>"` and focus lands on that region
instead. See
[features-implemented/document-navigator.md](features-implemented/document-navigator.md)
and the dialog manual.

**Errors.** `static/js/feedback.js` owns request feedback for surfaces that do
not: it marks the initiating control and the target busy, refuses a second
request from a busy control, restores both on success or failure, and reveals
one page-level `common.RequestFallback` for a failure nothing else reports. A
request inside `<dialog data-dialog>` belongs to `common/Dialog.js`; a live
region owns its own feedback and is left alone; the document save status and the
palette are never touched.

A failed **initial bundle** request is recoverable without a reload. The editor
loader in `layout/BlankPage.jinja` distinguishes loading from loaded and failed,
shows an Italian message with one `Riprova`, and retries on the same page;
`editorial/ReportPanel.js` does the same for the report bundle and still resumes
an active reproduction after the retry. `tests/frontend/test_report_panel.py`
covers failure, retry and resumption. The shortcut tests inject the bundle
directly, so they prove initialized editor behaviour, not loader recovery.

**Persistence.** One `AutosaveController` exists per API URL. It coalesces dirty
fields, sends authenticated JSON `PATCH` requests with the latest
`expected_version`, and flushes after about one idle second, at a five-second
ceiling, immediately at 200 changed characters, and on `Ctrl/⌘ + Enter`, blur,
htmx request intent, `visibilitychange` and navigation. `pagehide` sends one
keepalive request and keeps the local snapshot. Responses keep the draft: 409
offers an explicit retry against the latest version, 423 means locked, 401/403
and 422 keep the recovery panel. On mount, a differing local snapshot is never
applied silently — the reader chooses restore or discard. The full state list is
in [features-implemented/in-place-editing.md](features-implemented/in-place-editing.md).

**The command save barrier.** A command marked `data-requires-saved`
(publication, lock) waits for every controller's `settle()` before it runs, so it
cannot send stale content. A failed, conflicting or offline save rejects the
barrier, cancels the command and keeps its recovery panel; repeated clicks on
the same command are swallowed. The visible controls and
`Ctrl/⌘ + Shift + Enter` share the path. `tests/frontend/test_command_barrier.py`
covers the slow, conflicting, offline, repeated and clean cases.

**The saved-state indicator.** `common.SaveIndicator` is the single
`[data-autosave-status]` element per page: `role="status"`, `aria-live="polite"`,
hidden until the script writes text. The controller owns the text and
`data-state` (`saved`, `dirty`, `saving`, `error`, `conflict`);
`tests/frontend/test_save_indicator.py` covers its states, geometry and
small-text contrast. It reports the client's known outcome, not a server
commit.

## 9. The editor boundary

The editor mounts CodeMirror over the real Markdown source. The hidden source
textarea and the rendered block are not the editable textbox: CodeMirror builds
`.cm-content[role="textbox"]`, and that element carries the accessible name.

- `extensions()` passes the field's visible label to
  `EditorView.contentAttributes` as `aria-label`
  (`src/frontend/js/editor/index.js`). `DocEdit` and `DocSummary` publish their
  label as `data-doc-label` (`Testo Markdown`, `Sintesi`); the world-settings
  description uses `Descrizione del mondo`; the legacy Markdown field reads its
  textarea's label. `mountDocIdentity` names the input it inserts from
  `data-doc-label` or the visible eyebrow, and leaves the rendered heading as
  the level-one heading.
- `tests/frontend/test_editor_accessibility.py` asserts each actual open
  textbox's name and that the three names stay distinct.

**Leaving writing.** While a body or summary is open, the actions row shows a
labelled `Mostra il risultato` command. It runs the same close path as
`Ctrl/⌘ + Enter`: flush the pending write, render the result once, return focus
to the block, and resume at the same caret on reopen. It is touch-sized, appears
only while writing, and closing is neither publication nor discarding.
`tests/frontend/test_document_shortcuts.py` covers its visibility, flush, focus,
phone size and the reader/locked cases.

The editor's source lives in `src/frontend/js/editor/`; `static/js/editor.js` is
its built output. Rebuild with `npm run build:editor` and commit the bundle when
the source changes. The mount, preview, autosave and host rules are in
[features-implemented/in-place-editing.md](features-implemented/in-place-editing.md).

## 10. Prototyping and design work

The accepted process is
[development_processes/prototyping.md](development_processes/prototyping.md),
with repository conventions in [../prototypes/README.md](../prototypes/README.md).
Two modes were accepted on 2026-10-21: standalone static exploration, and
application-composed JinjaX studies for additions inside the existing atlas
identity. Bounded exemplars are
[document-layout-study](../prototypes/document-layout-study/README.md),
[appearance-study](../prototypes/appearance-study/README.md),
[collection-create-study](../prototypes/collection-create-study/README.md) and
[bookkeeping-study](../prototypes/bookkeeping-study/README.md).

The process owns the cycle, the equal-content comparison, revision evidence,
simulated-versus-real persistence and the handoff. This guide does not restate
it. What is **not** authorized: a redesign, a preview framework, production
routes, campaign reads or writes, migrations, promoting an experimental control
into the public vocabulary, or a competing `PRODUCT.md`/`DESIGN.md` authority.
The portable design process remains [design_guide.md](design_guide.md), and the
settled visual decisions remain
[features-request/frontend.md](features-request/frontend.md).

## 11. Worked examples

### A collection: characters

`src/frontend/components/pages/characters/CharacterList.jinja` composes the
masthead, then one `<common.Grid min="card" gap=5>` holding the entity cards and
`editorial.CollectionCreate` as the last cell. The create card is the collection:
with no characters it is the only cell, so there is no empty panel and no second
action. Below 700px the same button becomes the collection's action row above
the cards.

- Files: `pages/characters/CharacterList.jinja`,
  `editorial/CollectionCreate.jinja` and its stylesheet, `editorial/EntityCard`.
- Proof: `tests/frontend/test_character_list.py` mounts the real page
  (`test_populated_puts_the_create_card_in_the_grid`,
  `test_phone_puts_the_entry_above_the_collection`);
  `tests/frontend/test_collection_create.py` pins the placement, focus order and
  one-button rule.
- Limit: the page test proves composition and placement in Chromium; the POST
  and permission rule are covered by the collection-creation tests and the
  route, not by this component test.

### A host and its dialog: the invitation form

`pages/admin/AdminDashboard.jinja` declares the dialog's stylesheets and
`common/Dialog.js` on the host, renders an empty `#invite-dialog` container, and
its masthead button requests the fragment with `hx-target="#invite-dialog"
hx-swap="innerHTML"`. `pages/admin/InviteDialog.jinja` is a `common.Dialog` with
the form; it declares its own dependencies and carries no assets.

- Files: `pages/admin/AdminDashboard.jinja`,
  `pages/admin/InviteDialog.jinja`, `common/Dialog.jinja`/`.js`,
  `src/backend/users/views.py`.
- Proof: `tests/frontend/test_asset_delivery.py`
  (`test_a_raw_host_swap_styles_the_returned_fragment`,
  `test_repeated_swaps_keep_the_fragment_styled_and_initialized`);
  `tests/integration/test_admin_views.py`
  (`test_the_invite_dialog_fragment_relies_on_the_host_page`);
  `tests/e2e/test_admin_settings.py`
  (`test_inviting_from_the_masthead_swaps_the_table_and_keeps_focus`,
  `test_a_duplicate_invite_keeps_the_dialog_open_with_the_error`).
- Limit: these assert the invitation surface. They do not prove every dialog
  host declares its assets.

### A document field: the summary

`editorial/DocSummary.jinja` is one `[data-doc-summary]` block with a hidden
source textarea, a `[data-summary-render]` target, a hidden preview button that
targets `previous [data-summary-render]` with `hx-swap="innerHTML"`, and the
`Mostra il risultato` action. `mountDocSummary` mounts CodeMirror, registers the
field with the URL's autosave controller, and guards on `data-summary-ready`.

- Files: `editorial/DocSummary.jinja`, `editorial/DocSummary.css`,
  `src/frontend/js/editor/index.js` (`mountDocSummary`, `extensions`),
  `pages/characters/CharacterDetail.jinja` as the caller.
- Proof: `tests/frontend/test_command_barrier.py`
  (`test_the_summary_preview_replaces_only_the_rendered_children`,
  `test_a_mount_scan_after_the_preview_keeps_one_editor_and_one_write`);
  `tests/frontend/test_document_shortcuts.py`
  (`test_the_summary_has_the_same_close_command`);
  `tests/frontend/test_editor_accessibility.py`
  (`test_the_summary_textbox_is_named_after_its_visible_label`).
- Limit: the component tests prove the swap, guard and naming in Chromium. The
  persisted value is proven by the E2E autosave suite, which reads it back
  through the API.

## 12. Tests: what each command proves

| Layer | Command | Covers |
|---|---|---|
| Component | `uv run harness test frontend` | `tests/frontend/` only: real JinjaX markup in Chromium, the computed styles each test asks for, keyboard, focus, timers, htmx lifecycle. No backend, no database. |
| Unit | `uv run harness test unit` | `tests/unit/` only: template conventions and selector ownership (§3, §2), retired names, render-time option rejection, the token hook's fixtures, payload budgets and the icon registry. |
| Integration | `uv run harness env up --mode local`, then `uv run harness test integration` | a real database and the FastAPI app; server-rendered fragments, the host/fragment seam, persistence read back from the database. |
| E2E | `uv run harness env up --mode docker`, then `uv run harness test e2e` | the complete workflow as a black box, including real saves and navigation. |
| Tokens | `uv run harness material check` | the M3 inventory and `main.css` agree. |
| Request docs | `uv run harness backlog check-requests` | request frontmatter, IDs and relative links under `docs/features-request/`. It does not read this guide. |
| This guide | `uv run harness test unit -- tests/unit/test_frontend_guide_links.py` | every local link in this file resolves, and the guide links the manuals it defers to. |

**Compilation is checked separately.** The only compile check is
`tests/unit/jinja/test_templates_compile.py`. It is marked `unit` but
lives outside `tests/unit`, so `harness test unit` does not collect it, and the
integration profile selects `-m integration`, so it does not collect it either.
Run it by path: `uv run pytest tests/unit/jinja/test_templates_compile.py`.
It currently fails on `common/Button.jinja`, `common/Grid.jinja` and
`common/Pill.jinja` because its environment comes from `_build_templates` and
does not enable the `do` extension JinjaX uses; treat a rendering test as the
compile evidence until that guard is repaired. Rendering the component — as the
showcase smoke tests in `tests/unit/jinja/test_components_smoke.py` do — is what
catches a missing global or argument.

A component test mounts the real component with typed props and asserts the
contract in the browser:

```python
pytestmark = pytest.mark.frontend

def test_the_track_uses_the_spec_size(component):
    page = component.mount("common.Switch", props={"label": "Accenti", "name": "a"})
    assert page.locator(".switch__track").evaluate("el => getComputedStyle(el).width") == "52px"
```

Console or page errors fail the test, and every test leaves a screenshot and the
rendered HTML under `harness-artifacts/`. The fixture takes `content=`,
`htmx=True` and `reduced_motion=True`. A motion check is a component test with
`reduced_motion=True` that asserts the computed transition it names
(`tests/frontend/test_button_group.py::test_reduced_motion_disables_transitions`);
it is not a general motion audit.

**What a compile test does not catch:** an argument read before `{#def #}`
compiles and only fails when the page renders. Render the component, or rely on
the convention test. No command above proves CSS delivery, compilation, saving
or accessibility beyond the surfaces its own test exercises.

## 13. Git

- One ticket per change: implement, test, commit. A large change is never one
  commit.
- The pre-commit hooks include hooks that **rewrite files**
  (`jinjax-css-dependencies`, `ruff-format`, `end-of-file-fixer`). When that
  happens the commit fails; stage the rewritten files and commit again.
- Never co-author commits in this repository.
