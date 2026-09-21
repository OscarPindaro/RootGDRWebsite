# Frontend mega-plan — 2026-09-21

A critical, ticketed consolidation of Root GDR's frontend into one atlas design
system, one document-editing model, and one coherent collection language.

## Objective

Make the application feel designed as one product: a readable printed atlas with
predictable controls, strong information hierarchy, responsive document pages,
and accessible editing. Preserve the useful variety between covers, cards,
ledgers, stories, and atlas rows. Remove accidental variety caused by competing
CSS systems, copied page markup, legacy controls, and uncoordinated editor
widgets.

The goal is not fidelity to Material Design 3. Root GDR borrows component anatomy,
states, sizing discipline, and accessibility behavior from mature systems. Its
geometry, typography, color, elevation, and density come from the Root GDR
prototype.

## Settled product decisions

1. **Autosave remains the only save mode.** Do not add an autosave setting, a
   manual Save mode, or database-backed document version history. Preserve the
   existing local recovery, retry, and optimistic-concurrency behavior.
2. **Document order is Name → Title → Short description → Long description.**
   Types without a field omit it without leaving a navigation stop.
3. **Document navigation and text editing are distinct modes.** In navigation
   mode Arrow Up/Down changes block, Enter/F2 opens the focused block, and
   Tab/Shift+Tab remains valid sequential navigation. Inside CodeMirror, arrows
   retain native line/caret behavior. Ctrl/Command+Enter closes CodeMirror and
   returns focus to its block; Escape closes without moving.
4. **The world-access section remains named `Giocatori`.** It may display the
   owner, Masters, players, and pending invitations, with role/status columns
   making the distinction explicit.
5. **A literal creation card must be judged in the real application first.**
   Implement it on Characters, capture desktop and phone screenshots, and obtain
   visual approval before applying it to non-grid collections.
6. **Critical review outranks literal feedback.** A proposed fix may be replaced
   when investigation shows a different cause. Examples already established:
   backlinks below Characters are malformed composition rather than missing
   layout CSS; `Torna al mondo` is borderless because it requests a text variant,
   not because Button CSS failed to load.
7. **The consolidation may break internal frontend APIs.** Remove obsolete
   components, selectors, and compatibility aliases instead of preserving two
   systems. This permission applies to the entire application: shell, auth,
   admin, settings, search, content pages, and showcase. It does not waive the
   ticket, test, screenshot, documentation, or commit boundaries.

## Scope

### Included

- CSS ownership and component naming;
- the component showcase as the living visual contract;
- buttons, icon buttons, pills, fields, dialogs, confirmations, and tables;
- mastheads, collection create affordances, empty states, and collection grammar;
- document layout, backlinks, docbar hierarchy, and responsive behavior;
- ordered keyboard navigation across document fields;
- immediate visual updates for entity symbols/tints and the user symbol style;
- image-editor history placement and confirmation interactions;
- the World Settings `Giocatori` section;
- mention density;
- full-page structure, asset, accessibility, and screenshot checks;
- the global shell: Rail, Topbar, UserMenu, mobile drawer, and navigation;
- command-palette semantics, feedback, and focus management;
- Login/registration, authenticated landing, Settings, and Admin surfaces;
- application-wide pending, success, validation, permission, not-found, and
  server-error presentation;
- icon/font delivery and frontend payload budgets.

### Excluded

- manual saving and an autosave preference;
- database-backed content version history;
- a different Markdown engine or stored content format;
- collaborative real-time editing/CRDTs;
- changes to world membership policy or invitation-email delivery;
- replacing JinjaX/htmx with a client-side framework;
- widening prose to fill large displays beyond a readable measure;
- unrelated backend feature work.

## Roast: the current setup

### R1. Two skins own the same selectors

`src/frontend/static/css/main.css` carries the prototype's editorial classes,
while colocated `common/*.css` files carry an M3-shaped component library. Both
own generic selectors such as `.card`, `.pill`, and `.field`; legacy
`.btn--text` remains beside `.btn-text`. Computed appearance therefore depends
on cascade order and which JinjaX assets happen to be present.

The solution is not a single giant stylesheet. The target seam is:

- `main.css`: identity/alias tokens, reset, base typography, prose, and genuinely
  global document defaults;
- colocated component CSS: structure and states for that component only;
- page CSS: exceptional page composition only, never a reusable primitive;
- M3 inventories: provenance for adopted mechanics and dimensions, not a second
  visual identity.

Every reusable root selector gets one owner. Domain components use domain names
(`entity-card`, `document-layout`, `collection-create`) instead of colliding with
common primitives.

### R2. Product structures are copied instead of composed

Character, NPC, and Place details copy the same document wrappers and currently
mis-close them. CSS already defines a right backlinks column, but the Links panel
is nested inside the main grid child. Story detail can produce more than one
aside child; Session and Page detail use different layout rules again. There is
no shared, tested document layout contract.

### R3. Tests are locally strong and compositionally weak

Component tests cover geometry and keyboard behavior, but full-page tests do not
assert key DOM relationships or loaded computed styles. They did not catch the
malformed document grid, class collisions, or a text variant being mistaken for
missing CSS. The CSS dependency hook synchronizes referenced child assets, but
asset presence and page-level appearance require browser assertions.

### R4. The showcase contradicts settled design decisions

The showcase still advertises M3 Expressive sizes and round geometry after
stable atlas geometry was settled. It contains duplicate CSS directives and
specimens that are not representative of production pages. A living
specification that disagrees with the product cannot govern later work.

### R5. Editing is a set of widgets, not a document controller

`DocIdentity`, `DocSummary`, `DocEdit`, `Metadata`, and `ImageEditor` share an API
URL and autosave controller, but no owner defines block order, navigation mode,
active state, or focus return. Existing Tab behavior is incidental to DOM order
and removal of temporary inputs. The desired text-editor experience needs a
small document-level focus controller, not more page-specific key handlers.

### R6. Shared controls are incomplete or specialized in the wrong layer

- Field labels sit above both variants instead of implementing filled and
  outlined anatomy.
- ConfirmDialog is coupled to an admin htmx delete target and cannot serve as a
  generic confirmation primitive.
- ImageEditor hand-builds legacy-class buttons, owns a custom dialog shell, uses
  native browser confirmations, and reloads after choices and image operations.
- World membership uses Links as a table.
- Dialog exposes English close copy in an Italian interface and uses inline
  handlers.

### R7. The collection vocabulary lacks common states

Covers, entity cards, stories, ledgers, and atlas rows are valid different
representations. Their create, empty, draft, focus, count, and permission states
are not defined as one collection grammar. Current empty states often remove the
only in-context creation affordance, while every create action lives in the
masthead.

### R8. Several page-level symptoms have smaller causes

- The backlinks column is a wrapper bug.
- `Torna al mondo` needs the correct action variant, not another CSS hook.
- Masthead action alignment becomes mostly moot when creation moves into the
  collection.
- Unused horizontal space should hold navigation or backlinks; prose retains a
  readable measure.
- Symbol/tint changes reload because ImageEditor explicitly calls
  `location.reload()` after a successful PATCH.

### R9. The shell is visually central but structurally transitional

Rail, nav items, Topbar, scrim, and Palette still live in `main.css` rather than
with their components. UserMenu composes a primary Button and then overrides its
background, border, dimensions, radius, padding, and label wrapper until it acts
like an identity row. The mobile drawer moves focus in but does not trap it,
make the background inert, lock page scroll, or consistently restore the opener.
`Page.js` also assigns Arrow Up/Down to every link and button in the rail even
though a navigation landmark is not an ARIA composite widget; normal Tab order
is the predictable model.

### R10. Search looks like a command palette but lacks its interaction contract

Palette is a `div role="dialog"`, manually shown with a class, with a listbox that
contains links lacking option semantics. It does not restore focus, announce
loading or failure, expose the active result through `aria-activedescendant`, or
prevent focus leaving the modal. Every keystroke hits the database immediately.
It swallows request failures and rebuilds results through string HTML. This is a
promising feature that needs a real dialog/combobox model.

### R11. Auth, Home, Admin, and Settings belong to another application

The authenticated Home route contains only `Home` and a welcome sentence while
Worlds is the actual product entry point. Login is a generic elevated M3 card.
Admin uses a separate dashboard heading/table language and inline htmx handlers.
Settings is a lone form in a 900px box. These routes are part of the product and
must use the same masthead, rules, fields, dialogs, feedback, and responsive
rhythm as world content.

### R12. System feedback, failure pages, and delivery are unfinished

There is no application-wide htmx pending/error treatment, and Alert always uses
assertive `role="alert"` even for ordinary success/info. Most HTTP errors fall
back to framework responses rather than designed Italian 403/404/500 pages. The
screenshot suite covers only a fraction of routes. Every page downloads the
roughly 408 KB Lucide runtime and then replaces icon placeholders in the browser,
although htmx swaps require repeated initialization and the project already has
server-side SVG machinery. Fonts are render-blocking third-party requests, so
network availability can change both first paint and screenshot geometry.

## Target architecture

### CSS and tokens

- Identity tokens remain the source for paper, ink, tints, typography, rules,
  radius, hard offsets, spacing, and semantic state.
- Common components consume alias tokens and expose stable markup/state APIs.
- Product components consume the same tokens; they do not redefine common
  controls.
- No selector is defined by both `main.css` and a colocated component stylesheet.
- Dynamic tint values may remain custom properties (`--c`, `--p*`); layout and
  component geometry may not be inline page styles.
- Hard offset elevation is reserved for openable/interactive surfaces. Focus is
  always visible independently from hover.

### Document editing

A document root owns an ordered list of editable blocks. Each block exposes:

- a stable block element focusable in navigation mode;
- an `open()` operation;
- a `close()` operation that restores focus to the block;
- whether arrows are currently owned by an internal editor;
- its autosave field name and current state.

The existing AutosaveController remains the only persistence path. The document
navigator coordinates focus and opening; it does not duplicate persistence.

### Collections

Every collection declares:

- representation: cover, entity card, story card, ledger, or atlas;
- empty state;
- creation entry;
- draft representation;
- primary metadata and count;
- read/manage permissions;
- desktop and phone shape.

A shared creation contract may have multiple skins only after the literal card
prototype has been reviewed.

### Shell and overlays

The shell is one layout system. Rail and Topbar share navigation semantics;
UserMenu is an identity/menu trigger rather than a reskinned CTA. On phone the
rail is a modal drawer with contained focus, inert background, scroll lock,
Escape/scrim close, and opener restoration. Ordinary navigation links use
native Tab order. Menus and true composite widgets alone own arrow-key movement.

Palette is a modal search dialog containing an editable combobox. DOM focus stays
in the input while the active result is exposed with `aria-activedescendant`;
Arrow keys change the active option, Enter follows it, Escape closes, and focus
returns to the opener. Loading, empty, aborted, offline, and server-error states
are distinct and announced appropriately.

### System feedback and delivery

Htmx actions expose pending state on the initiating control/region, prevent
accidental duplicate submission, and place validation or request failure beside
the affected operation. Autosave retains its dedicated status and recovery
surface. Success/info messages are polite status messages; destructive or
blocking errors are alerts. Authenticated HTML requests receive designed Italian
403/404/500 pages with a safe route back into the product.

Icons render as server HTML or a small static SVG sprite; no full icon runtime is
required on every page and htmx swaps need no icon re-initialization. Product
fonts are self-hosted with their licenses, preload only critical faces, use
`font-display: swap`, and retain metric-compatible fallbacks. The editor bundle
remains lazy and separate from reading pages.

## Global definition of done

Every ticket below is implemented, tested, documented, visually checked, and
committed before the next begins.

For each ticket:

1. update or add the relevant frontend/unit/integration/E2E tests;
2. run `uv run harness test unit` and the focused suite;
3. run `uv run harness test frontend` for component/geometry changes;
4. use the harness environment appropriate to integration/E2E work;
5. capture desktop and 390×844 phone screenshots of every affected page;
6. compare mapped pages with `prototypes/devin-prototype/`;
7. inspect browser console errors and focus behavior;
8. run the applicable automated accessibility scan plus a manual keyboard pass;
9. record shell CSS/JS payload changes for delivery-sensitive tickets;
10. write or update one short file in `docs/features-implemented/` and its index;
11. commit only that ticket, without co-authorship.

A visual ticket is not complete with tests alone. A data-writing browser flow
must assert persisted state through the API or integration database.

## Ticket sequence

### F1 — Establish CSS ownership and enforce the seam

**Purpose:** prevent new collisions before migrating existing ones.

**Changes**

- Update `docs/frontend_guide.md` so `main.css` has the restricted target role
  described above; replace the transitional rule that editorial classes may
  continue accumulating there.
- Add an explicit selector-ownership inventory for global foundations and
  colocated components.
- Extend `src/pre_commits/jinjax_css_dependencies/` so a component with a sibling
  stylesheet cannot be rendered without its own asset and so transitive assets
  remain synchronized for htmx fragments.
- Add a static convention test that reports root selectors owned by more than
  one stylesheet. Start with targeted reusable roots (`card`, `pill`, `field`,
  `button`, `dialog`, `table`) and an explicit temporary migration allowlist;
  remove allowlist entries in later tickets.
- Add a representative browser asset test that renders a full page and an htmx
  fragment and checks computed styles, not only `<link>` presence.
- Fix the duplicate `{#css #}` directive in `pages/showcase/Showcase.jinja` as
  part of making the guard pass.

**Files**

- `docs/frontend_guide.md`
- `src/pre_commits/jinjax_css_dependencies/hook.py`
- `tests/unit/test_jinjax_css_dependencies.py`
- `tests/unit/jinja/test_component_conventions.py`
- representative frontend asset tests
- `pages/showcase/Showcase.jinja`

**Acceptance**

- Omitting a component's own stylesheet fails before commit with the component
  and asset named.
- A duplicate reusable root selector fails with both owner paths named.
- A full-page and fragment render prove Button and Field computed styles load.
- Existing app pages still render before visual migration begins.

### F2 — Repair and standardize the document layout

**Purpose:** fix backlinks immediately and remove copied wrapper bugs.

**Changes**

- Add a document-layout variant to the existing layout primitives, with one main
  child and one optional aside stack; do not create another page-specific grid
  class in `main.css`.
- Migrate Character, NPC, Place, Story, Session, and Page details to the same
  composition contract.
- Character/NPC/Place Links become a direct right-column child on desktop.
- Story's included sessions and backlinks share one aside stack rather than
  becoming competing grid columns.
- Session backlinks and pager follow a deliberate document/aside/footer
  hierarchy.
- Page detail reconciles `Altre pagine` and backlinks in one aside.
- At the phone breakpoint the aside stacks below the document. Prose retains its
  readable measure on wide displays.

**Files**

- `common/Grid.jinja`, `common/Grid.css` (or one clearly justified editorial
  layout component if Grid cannot express the semantic contract)
- all six `pages/*/*Detail.jinja` files
- document-layout rules migrated out of `main.css`

**Tests**

- Browser geometry assertions: aside right of main at desktop and below at phone.
- DOM assertions: exactly one direct main child and at most one direct aside.
- Character/NPC/Place render tests with and without backlinks.
- Story test with sessions and backlinks simultaneously.

**Acceptance**

- Fiamma Rossa's `Collegamenti` is visibly right of the document at desktop.
- No prose line becomes wider merely to fill the vacated space.
- All detail pages share the same breakpoint and spacing contract.

### F3 — Consolidate Button, IconButton, link actions, and Pill

**Purpose:** remove the most visible M3/editorial collision and separate state
from commands.

**Changes**

- Make `common.Button` the only action-button markup. Remove production uses of
  `.btn--text`, raw `.btn` markup, non-existent `ghost` variants, and duplicated
  Tooltip wrappers.
- Skin default controls with stable atlas geometry: low/square radius, ink rules,
  flat fills, and hard-offset interaction only where justified. Keep the 44px
  phone touch target and visible focus.
- Keep icon-only controls square with required tooltip/accessibility labels.
- Make `common.Pill` the only status pill. Add the product variants required for
  draft, published, owner/player/master, and current scene; use low-radius atlas
  geometry instead of a full capsule unless the prototype explicitly requires a
  capsule.
- Rename the world-settings back action to Italian UI copy if needed and select
  an outlined/secondary variant so its border is intentional.
- Convert Overview section links to Button link variants or a dedicated textual
  link component with one owner.
- Remove migrated `.btn--text` and duplicate `.pill` rules from `main.css` and
  remove their selector-guard exceptions.

**Files**

- `common/Button.*`, `common/IconButton.jinja`, `common/Pill.*`
- `editorial/Docbar.jinja`
- `pages/worlds/WorldOverview.jinja`, `WorldSettings.jinja`
- detail-page callers and ImageEditor fallback markup
- Button/Pill M3 provenance inventories
- showcase specimens

**Tests**

- Existing stable-geometry and IconButton accessibility tests.
- New variant snapshots via computed border/radius/fill assertions.
- No legacy action classes in production templates/scripts.
- Phone touch-target and overflow checks.

**Acceptance**

- No oval action appears by accident in an atlas surface.
- State pills are visually quieter than commands.
- `Torna al mondo` has the chosen intentional border without adding redundant CSS.

### F4 — Rebuild Field around M3 anatomy with the atlas skin

**Purpose:** make Filled and Outlined real component variants.

**Changes**

- Keep semantic native `input`, `textarea`, and `select` controls.
- Filled: label lives inside the filled container and moves to its populated/
  focused position; the active indicator is the bottom rule.
- Outlined: label occupies a notch in the outline when focused or populated.
- Supporting/error text stays below the container; required, disabled, error,
  focus, populated, placeholder, select, and textarea states are explicit.
- Consume existing field/touch/typography tokens and update the M3 inventory for
  adopted dimensions. Retain Root GDR paper, ink, radius, and focus color.
- Replace remaining legacy `.field` global ownership and remove the guard
  exception.
- Update Combobox to compose or visually align with the Field anatomy rather
  than maintaining a third text-control skin.

**Files**

- `common/Field.jinja`, `Field.css`
- `common/Combobox.*`
- field token inventory and `main.css` aliases
- showcase and all form callers

**Tests**

- Browser tests for empty/populated/focused/error/disabled variants.
- Label position and outline continuity for Filled and Outlined.
- Select/textarea/keyboard/focus behavior.
- No separate top label in either requested variant.

**Acceptance**

- The World Settings add-player dialog matches the supplied M3 anatomy while
  remaining visibly part of Root GDR.
- Label and error semantics remain available to assistive technology.

### F5 — Make Dialog and confirmation interactions genuinely reusable

**Purpose:** replace native confirmations and specialized overlay behavior with
one accessible application pattern.

**Changes**

- Generalize `common.Dialog` and `common.ConfirmDialog`; remove admin-specific
  targets and HTTP methods from the common component.
- Use Italian close labels and remove inline `onclick` behavior in favor of the
  component's colocated script.
- Define focus entry, focus trap/native dialog behavior, Escape, cancel, pending,
  error, destructive confirmation, and opener-focus restoration.
- Migrate admin invitation confirmation and all ImageEditor restore/delete/clear
  confirmations.
- Do not silently replace every htmx `hx-confirm` in this ticket; inventory them
  and migrate destructive document actions with Docbar in F10.

**Files**

- `common/Dialog.*`, `common/ConfirmDialog.jinja` and colocated JS
- `pages/admin/InviteDialog.jinja`
- `editorial/ImageEditor.jinja/.js`
- dialog tests and image-editor E2E tests

**Acceptance**

- No `window.confirm` remains in ImageEditor.
- Restore, delete revision, and remove current image show action-specific copy.
- Failed requests keep the dialog open and expose an adjacent live error.
- Focus returns to the exact invoking control after cancel or completion.

### F6 — Finish ImageEditor as a live component

**Purpose:** remove reload-driven interactions and place history where it belongs.

**Changes**

- After animal/shape/tint PATCH, update the visible face and selected state from
  the successful response without `location.reload()`.
- Preserve an uploaded image while changing metadata; when the fallback face is
  visible, clone/render the selected ChoiceGrid mark into it and update its tint.
- Restore/delete/clear updates the current media and revision list in place where
  the API response is sufficient. Add the smallest response data only if a 204
  response cannot update the UI correctly; do not redesign image persistence.
- Give ImageEditor a stable history-dialog id and support an external labelled
  trigger.
- In World Settings place the history IconButton in `SectionHead`, on the same
  line as `Copertina`, aligned right. Character/NPC/Place keep a compact local
  image command row unless the screenshot review supports the heading pattern
  there too.
- Use only shared Button/Dialog/Stack controls in template and generated DOM.

**Files**

- `editorial/ImageEditor.jinja/.css/.js`
- `pages/worlds/WorldSettings.jinja`
- image routes only if response data is demonstrably missing
- image component and E2E tests

**Acceptance**

- Selecting a tint or symbol updates immediately and persists through the API.
- No selection, restore, delete, or clear requires a page reload.
- World-cover history is at the far right of the Copertina heading on desktop
  and remains reachable on phone.
- Dialog focus and image API state are asserted.

### F7 — Add the ordered document navigator

**Purpose:** make in-place editing feel like one vertical text editor.

**Changes**

- Mark editable blocks with one shared contract and register them in visual
  document order, independent of incidental nested DOM order.
- Add a small document navigator in `src/frontend/js/editor/index.js`; keep it in
  that file rather than fragmenting single-use behavior into multiple helpers.
- Navigation mode:
  - Arrow Down/Up focuses the next/previous editable block;
  - Tab/Shift+Tab follows the same logical sequence while respecting other page
    controls;
  - Enter/F2 opens the focused block;
  - the focused block gets one visible active treatment and scrolls into view
    with `block: nearest` when needed.
- Single-line identity edit mode:
  - Arrow Down commits and closes, then focuses the next block;
  - Arrow Up commits and closes, then focuses the previous block;
  - Enter commits and returns to the same block;
  - Escape closes and returns to the same block without moving.
- CodeMirror mode:
  - arrows remain native;
  - Ctrl/Command+Enter closes and returns focus to that block;
  - Escape closes and returns focus without moving;
  - after close, Arrow Down/Up navigates between blocks.
- Add visible `Sintesi`/Short description labeling where currently absent.
- World Settings uses the same contract for Name → Description.
- Preserve AutosaveController unchanged except for focus/flush integration
  required by the navigator. Autosave remains the only save mode.

**Files**

- `editorial/DocIdentity.*`, `DocSummary.*`, `DocEdit.*`
- all detail templates for labels/order
- `src/frontend/js/editor/index.js` and rebuilt static bundle
- world settings identity markup

**Tests**

- E2E keyboard journey across every block on Character.
- Native Arrow behavior inside short and long CodeMirror editors.
- World Settings Name → Description journey.
- Locked/read-only pages expose no edit navigation.
- API assertions after each edited field; conflict/offline tests remain green.

**Acceptance**

- Name → Title → Short description → Long description is deterministic.
- Opening and closing never loses focus or unexpectedly changes block.
- Existing autosave timing, local recovery, and 409 behavior remain intact.

### F8 — Apply symbol-style preferences immediately

**Purpose:** make account visual preferences visibly effective at selection time.

**Changes**

- Keep server-side persistence and first-render resolution from
  `current_user.symbol_style`.
- Render role marks in a form that can switch between equivalent icon and shape
  presentations without a full page reload, or return one targeted rail fragment
  if that is smaller and preserves server authority.
- On a successful Settings htmx response, update the active symbol style for the
  current document and every visible role mark immediately.
- Do not conflate this account preference with entity animal/shape/tint choices;
  F6 owns those.
- Preserve no-JavaScript form submission and server-rendered correctness.

**Files**

- `common/Mark.jinja` and its owned CSS/optional small JS
- `layout/Rail*.jinja`
- `pages/settings/Settings.jinja`, `SettingsStatus.jinja`
- `users/views.py` only as required for a targeted response

**Tests**

- Settings integration test persists the enum.
- Frontend/E2E test selects Shapes and sees rail/visible marks change before
  reload, then reloads and sees the same server-rendered state.
- Keyboard selection behaves identically to pointer selection.

**Acceptance**

- No extra Enter or reload is required after selecting Icons or Shapes.
- All visible instances agree on one style.

### F9 — Redesign World Settings `Giocatori`

**Purpose:** replace the exposed inline form and misuse of Links with a clear
access-management surface.

**Changes**

- Create page-domain components for the players table/list and add-player dialog;
  reuse common Table, Field, Dialog, Pill, IconButton, and Alert.
- Keep the section title `Giocatori`.
- Put a plus IconButton in the section heading. It opens the dialog.
- Present person/email, role, status, and actions as explicit columns. Mark the
  owner, Masters, players, and pending invitations visibly.
- The dialog accepts email and role. Existing users become members; unknown
  emails follow the already implemented pending invitation flow.
- Keep validation/notices adjacent to dialog fields. On success update the table
  and close the dialog without a full-page redirect if the existing view can
  return a focused fragment cleanly.
- Replace remove/revoke `hx-confirm` with the shared confirmation dialog.
- Preserve the owner removal prohibition and existing invitation policy.

**Files**

- `pages/worlds/WorldSettings.jinja/.css`
- new page-domain table/dialog components only where reuse justifies them
- `worlds/views.py` fragment responses
- existing invite/member services unchanged unless a real service gap is found

**Tests**

- Component tests for table rows and dialog Field anatomy.
- Integration tests for existing-user add, external invite, duplicate/upsert,
  revoke, remove, owner protection, and authorization.
- E2E dialog workflow with API/database persistence assertions.
- Desktop table and phone stacked/scrollable treatment screenshots.

**Acceptance**

- No inline add form remains on World Settings.
- Plus opens an accessible dialog.
- Pending and active access are distinguishable without reading sentence-like
  row text.

### F10 — Recompose Docbar into status and command regions

**Purpose:** remove uppercase metadata interleaved with buttons and establish one
command hierarchy.

**Changes**

- Give Docbar explicit status and action regions. Publication, ownership/current
  scene, and similar facts stay together; edit/lock/publish/delete commands stay
  together.
- Use shared Pill and Button/IconButton only.
- Keep destructive actions visibly distinct and confirmed through the shared
  dialog.
- Choose icons only where recognition is strong; retain text for ambiguous state
  transitions such as `Riporta a bozza`, or combine icon plus text. Tooltips do
  not compensate for unclear primary actions.
- Define phone behavior without a blind horizontal strip mixing statuses and
  commands; statuses wrap above a compact command row or overflow menu.
- Apply the same contract to all six document types.

**Files**

- `editorial/Docbar.jinja` plus a new colocated stylesheet
- all detail callers
- migrated docbar rules removed from `main.css`
- destructive-action view fragments only if required by confirmation handling

**Tests**

- Unit rendering of status/action regions per state and permission.
- Frontend geometry at desktop/phone.
- E2E lock, publication, current scene, cancel draft, and delete confirmation.

**Acceptance**

- No status pill is a child of the command region.
- The same command has the same placement and visual treatment on every document.
- Phone controls remain 44px targets and do not hide destructive context.

### F11 — Reduce mention weight without losing semantic identity

**Purpose:** restore prose rhythm.

**Changes**

- Reduce inline padding, icon size/gap, border emphasis, font weight, and radius.
- Remove negative inline margin that crowds surrounding text.
- Preserve tint, kind icon, missing-reference state, hover, and visible focus.
- Keep live-preview and server-rendered markup visually equivalent by sourcing
  their values from shared CSS variables rather than duplicated literal styling
  in the CodeMirror theme where possible.

**Files**

- mention rules moved to an owned editorial/prose stylesheet
- `src/frontend/js/editor/index.js` theme only where CodeMirror requires it
- `live-preview.js` semantics unchanged
- mention style tests and rebuilt bundle

**Acceptance**

- Mentions in Fiamma Rossa read as links within a sentence, not chips interrupting
  the line.
- Render and edit states match in size, radius, and weight.

### F12 — Prototype the literal creation card on Characters

**Purpose:** validate the disputed visual direction with evidence before a broad
rollout.

**Changes**

- Add one accessible literal creation card to the Character grid using the warm
  paper surface, ink border, stable square-ish plus treatment, and the same grid
  footprint as entity cards.
- Reuse the existing draft-first POST route and preserve no-JavaScript behavior.
- Remove the Character masthead plus for this prototype so the comparison is not
  biased by duplicate actions.
- Handle empty Characters by showing the creation card as the collection itself,
  not a separate empty panel plus another action.
- Implement the component narrowly enough to delete or generalize after review;
  do not roll it out elsewhere in this ticket.

**Files**

- one clearly named collection-create component and CSS
- `CharacterList.jinja`
- showcase specimen
- Character list tests

**Visual checkpoint**

Capture and present:

- populated desktop;
- empty desktop;
- populated 390×844 phone;
- empty phone;
- focus and hover states;
- side-by-side with the old masthead action and the prototype's world
  `.cover--new` treatment.

**Acceptance**

- User approval is required before F13.
- The card is a real button/link semantic with a clear accessible name and focus.
- Creation still persists a draft and lands in one-shot name editing.

### F13 — Define and roll out the approved collection creation grammar

**Gate:** begin only after F12 screenshot approval.

**Default direction to evaluate:** preserve the approved literal card visual
language. For grids it occupies a normal cell. For ledger/atlas collections,
prototype its placement without changing all content into cards; if a literal
card damages scanning, stop and record that evidence before choosing a row
adaptation. Do not silently reinterpret the approval.

**Candidate pages**

- Worlds, Characters, NPCs, Places, Sessions, Stories, Pages;
- master/manage permissions only where creation is restricted;
- populated and empty states;
- drafts remain separate from creation.

**Changes after approval**

- Remove redundant masthead create buttons from approved pages.
- Keep non-creation masthead commands centered in a stable, intentional aside;
  remove the aside entirely when empty.
- Make the shared creation entry own hover/focus/pressed/disabled behavior and
  action semantics; pages choose only the route, label, and approved
  presentation.
- Delete now-unused `.cover--new`/empty-state duplicates or make them the shared
  implementation rather than parallel CSS.

**Tests and acceptance**

- One create-flow test per distinct route behavior (world form versus draft-first
  content POST), not per duplicated template.
- Desktop/phone screenshots for every collection, both populated and empty.
- No page exposes two equally prominent create controls.
- A denied role never receives a create entry.

### F14 — Componentize the collection language

**Purpose:** solve the deeper inconsistency exposed by creation placement.

**Changes**

- Rename `editorial.Card` to a domain-specific `EntityCard` with an
  `.entity-card` root; migrate Character/NPC draft callers and remove collision
  with `common.Card`.
- Determine whether `common.Card` is still a valid generic surface. Delete the
  unused `pages.worlds.WorldCard`; keep or rename the common surface only for
  real callers such as Login/showcase.
- Extract repeated story-card, ledger, and atlas-row structures into the minimum
  set of product components that have multiple callers. Do not create helpers
  for one-off snippets.
- Define shared focus, openable hard-offset hover, draft/status, metadata, and
  phone rules while preserving each representation's information density.
- Move their rules from `main.css` to colocated CSS and remove selector-guard
  exceptions.
- Align EmptyState with the approved creation grammar.

**Files**

- editorial collection components and list-page callers
- `common/Card.*` only if retained
- list templates and migrated sections of `main.css`
- showcase specimens and component tests

**Acceptance**

- Common Card and entity cards no longer share a selector.
- Sessions remain a ledger, Places remain an atlas, Stories retain story bands,
  and all have consistent interaction/state rules.
- No copied collection structure with two or more callers remains inline.

### F15 — Rebuild the global shell as one accessible layout

**Purpose:** make Rail, Topbar, drawer, and user identity behave as one system on
every authenticated route.

**Changes**

- Move Rail, RailItem, Topbar, scrim/drawer, and shell rules out of `main.css`
  into their owning layout components.
- Replace UserMenu's primary Button plus extensive CSS overrides with a dedicated
  identity/menu trigger whose markup directly expresses avatar, name/email, and
  chevron. Reuse Menu behavior without pretending the trigger is a CTA.
- Remove global Arrow Up/Down interception across every rail link/button. Keep
  ordinary navigation in native Tab order; Menu retains its own APG arrow model.
- Make the phone rail a complete modal drawer: initial focus, contained Tab/
  Shift+Tab, inert background, body scroll lock, Escape and scrim close, and
  opener focus restoration. Closing via a selected navigation link may navigate
  normally without a visible intermediate jump.
- Give Topbar one compact phone hierarchy: drawer trigger, truncated page/world
  identity, and search action. Remove inline layout styles.
- Keep the desktop rail sticky for viewport navigation while its background spans
  the full document height. Long page navigation and long user identities must
  scroll/truncate without hiding the user menu.
- Reconcile global and in-world navigation labels/counts, current-page state,
  focus state, and icon/shape preference after F8.

**Files**

- `layout/Page.jinja/.css/.js`
- `layout/Rail.jinja` plus new colocated CSS if needed
- `layout/RailItem.jinja`
- `layout/Topbar.jinja` plus colocated CSS
- `layout/UserMenu.jinja/.css`
- migrated shell sections removed from `main.css`

**Tests**

- Desktop rail geometry and full-document-height checks.
- Phone drawer focus containment, inert background, scroll lock, Escape/scrim
  close, and focus restoration.
- Long world name, long email, many static pages, Master/Player/global nav.
- Menu keyboard tests remain isolated from ordinary nav Tab behavior.

**Acceptance**

- Shell behavior and appearance are identical across Worlds, content, Settings,
  Admin, and Home/redirect destinations.
- No generic Button override is required to render user identity.
- Keyboard users never move behind an open drawer.

### F16 — Rebuild the command palette as a dialog/combobox

**Purpose:** turn the existing database search into a complete accessible command
surface.

**Changes**

- Compose the palette from the shared Dialog mechanics and an editable combobox
  contract rather than a manually shown `div role="dialog"`.
- Keep DOM focus in the query input. Expose the active result with
  `aria-activedescendant`; results have stable option ids and accessible kind/name
  text. Arrow Up/Down changes the active result, Enter follows it, Escape closes,
  and focus returns to whichever search trigger opened it.
- Debounce queries briefly, abort stale requests, and ignore out-of-order
  responses. Keep the server as the permission authority.
- Distinguish initial/loading, results, empty, offline, unauthorized, and server
  failure states. Announce result count and errors politely without repainting
  focus.
- Build result DOM with text nodes/properties rather than HTML strings.
- Preserve `Alt+Space` and Ctrl/Command+K, document the shortcuts in both desktop
  rail and phone Topbar, and avoid conflicts with browser/editor shortcuts.
- Move Palette styles from `main.css` to the component.

**Files**

- `layout/Palette.jinja/.css/.js`
- shared Dialog/Combobox contracts only where real reuse exists
- `backend/palette.py` only if response metadata required by the accessible UI is
  missing
- Rail and Topbar opener markup

**Tests**

- Component browser tests for open/close/focus, active descendant, arrow/home/end,
  Enter, Escape, empty/loading/error, stale-response suppression, and both hotkeys.
- Integration tests retain permission-filtered search results.
- Phone dialog geometry and software-keyboard-safe height.

**Acceptance**

- Focus cannot escape an open palette.
- Closing always restores the correct opener.
- Network failure is visible and retryable rather than silently looking empty.

### F17 — Replace the placeholder landing page and redesign authentication

**Purpose:** make the first and unauthenticated experiences part of Root GDR.

**Changes**

- Remove the empty authenticated Home page and its redundant global-nav item.
  Redirect authenticated `/` to `/worlds`, which is the real product entry point,
  unless a later feature supplies a genuine cross-world dashboard.
- Delete dead Home component/CSS after route and navigation tests move.
- Redesign Login/registration as an atlas cover/colophon surface using the final
  Field, Button, Alert, Divider, and surface primitives. Do not use a generic M3
  elevated card or introduce a second marketing design language.
- Preserve password, Google, invitation-only registration, development login,
  no-JavaScript forms, and existing redirects.
- Place validation at the relevant form and focus the first invalid field or
  summary appropriately after htmx replacement.
- Ensure password-manager/autocomplete semantics, visible labels, error copy,
  focus order, reduced motion, phone safe areas, and long translated text.

**Files**

- `backend/views.py`, `backend/navigation.py`
- delete `pages/home/Home.jinja/.css`
- `pages/login/Login.jinja/.css`
- auth view tests and route coverage

**Tests**

- Unauthenticated `/` redirect, authenticated `/` redirect, and active global
  navigation.
- Login/register success and each validation/invitation error.
- Google/dev variants render only when enabled.
- Desktop/phone screenshots for login, registration, and error state.

**Acceptance**

- There is no placeholder destination in primary navigation.
- Auth looks unmistakably like the same product without exposing authenticated
  shell controls.

### F18 — Bring Admin and Settings into the atlas system

**Purpose:** remove the last generic-dashboard surfaces.

**Changes**

- Recompose Admin with Masthead, SectionHead, final Table, Pill, Dialog, and
  IconButton contracts; remove inline htmx JavaScript in favor of component
  events/behavior.
- Define responsive table behavior deliberately: retain a real table where
  column comparison matters, add labelled compact rows on phone rather than
  relying only on horizontal overflow.
- Give empty user/invitation states, pending/revoked/accepted status, and actions
  the same hierarchy as world membership.
- Recompose account Settings as a real settings page with grouped preference
  rows, explanatory copy, immediate symbol-style behavior from F8, and scoped
  polite feedback. Do not add autosave or manual-save controls.
- Ensure Admin permissions, invitation dialogs, confirmation dialogs, and htmx
  partial replacements retain heading context and focus.

**Files**

- `pages/admin/*`, `pages/settings/*`
- `common/Table.*` if responsive semantics need extension
- `users/views.py` partials only where needed
- Admin/Settings component, integration, and E2E tests

**Acceptance**

- Admin and Settings share the application's title, spacing, control, and
  feedback language.
- Phone tables remain understandable by row without losing header associations.
- No inline event-handler JavaScript remains in these pages.

### F19 — Add application-wide request feedback and designed error pages

**Purpose:** make waiting and failure predictable beyond autosave.

**Changes**

- Add a small global htmx lifecycle controller that marks the initiating control
  and target region busy, prevents duplicate submit, preserves control width,
  and restores state after success or failure. Use text/ink-rule feedback rather
  than decorative spinners unless progress is genuinely indeterminate and long.
- Keep validation and operation errors local. Add a page-level fallback only for
  unhandled htmx failures; do not turn every success into a toast.
- Extend Alert semantics: success/info default to polite status, warning may be
  status, and blocking/destructive errors use alert. Callers choose when the
  distinction is contextual.
- Add Italian HTML 403, 404, and 500 pages composed from BlankPage/Page primitives,
  with request-safe copy, request id where useful, and a route back to Worlds or
  Login. JSON API requests retain JSON error responses.
- Audit empty states, permission-denied controls, offline search, image failures,
  invite errors, and autosave recovery so each has one owner and no duplicate
  banners.

**Files**

- one small shell/htmx feedback script and owned CSS
- `common/Alert.*`
- new page error component(s) only as required
- server exception/content-negotiation registration
- representative forms and htmx fragment callers

**Tests**

- Frontend tests for busy/disabled/width-stable/request-failure behavior.
- Integration tests for HTML versus JSON 403/404/500 responses.
- E2E duplicate-submit prevention and focus after validation failure.
- Screenshots of 404, 403, login error, invite error, and offline palette.

**Acceptance**

- No htmx action fails silently or can be submitted twice accidentally.
- Ordinary success is not announced assertively.
- Browser navigation never exposes a raw framework error payload.

### F20 — Remove runtime icon replacement and stabilize font delivery

**Purpose:** reduce baseline payload, eliminate htmx icon re-initialization, and
make typography deterministic.

**Changes**

- Inventory the actual icon names used by `common.Icon` and Button callers.
- Generate/commit a minimal licensed SVG sprite or server-side icon registry from
  the pinned Lucide source, and render `<svg>`/`<use>` markup directly in JinjaX.
  Unknown icon names fail tests instead of silently disappearing.
- Remove `lucide.min.js`, `lucide-init.js`, global `createIcons()` calls, and all
  htmx post-swap icon initialization. Keep role marks separate because they are
  product semantics, not Lucide UI icons.
- Replace per-instance pixel style attributes in Icon with size classes/tokens.
- Self-host the selected Newsreader and IBM Plex WOFF2 subsets with their license
  files; preload only the critical regular faces, use `font-display: swap`, and
  preserve the documented fallback stacks. Do not download floating `latest`
  assets during builds.
- Record raw and compressed budgets for base CSS, shell JavaScript, icon assets,
  fonts, and the separately lazy editor. Add a regression check with explicit
  thresholds and documented exceptions.
- Verify static caching headers/fingerprinting behavior supported by the existing
  deployment; do not add a new asset pipeline unless the current one cannot cache
  immutable assets safely.

**Files**

- `common/Icon.jinja` and generated/pinned icon source
- `layout/BlankPage.jinja`
- static font/icon assets and license files
- remove Lucide runtime files/references
- package/build scripts only if deterministic generation is required
- payload-budget tests/documentation

**Acceptance**

- Reading pages download no Lucide runtime and htmx swaps need no icon pass.
- Every production icon renders on the server and inherits current color.
- Typography remains stable when external networks are unavailable.
- Base payload budgets are measured and enforced; editor weight stays off
  read-only pages.

### F21 — Final responsive and visual pass

**Purpose:** evaluate the product as pages rather than isolated components.

**Audit matrix**

- Worlds list/new;
- World Overview and Settings;
- every collection populated/empty;
- representative Character, NPC, Place, Session, Story, and Page details;
- Settings, dialogs, menus, autocomplete, image history, recovery/conflict;
- unauthenticated Login and registration, including validation failures;
- Admin users and invitations, populated and empty;
- command palette loading/results/empty/offline/error;
- 403, 404, and 500 HTML pages;
- desktop rail and phone drawer with long navigation/user data;
- component showcase;
- anonymous, Admin, Master, and Player permissions where layouts differ;
- desktop and 390×844 phone, plus one wide desktop check for reading measure.

**Review**

- typography hierarchy and readable measure;
- spacing rhythm and alignment;
- border/radius/elevation consistency;
- icon versus shape language;
- state versus action hierarchy;
- keyboard order, focus, and touch targets;
- overflow and long Italian copy;
- reduced motion and contrast;
- full-page and htmx-fragment asset loading;
- console/network errors.

**Changes**

Fix only systemic or local defects revealed by the matrix. Do not introduce a
new redesign direction in this cleanup ticket. Update `seed/prototype_map.yaml`
landmarks where new component roots replaced legacy selectors.

**Acceptance**

- Every mapped page has reviewed desktop and phone compare output.
- No unexplained horizontal overflow at 390px.
- No missing component asset or browser console error.
- Keyboard-only journeys cover shell/drawer navigation, command search,
  authentication, collection creation, document editing, image history, Admin
  invitation, and world-player invitation.
- Automated accessibility scans have no unreviewed serious/critical findings;
  automated results supplement rather than replace the manual keyboard review.
- Base payload and lazy-editor budgets remain within the thresholds set in F20.

### F22 — Remove the transitional frontend system

**Purpose:** finish consolidation instead of leaving permanent compatibility
layers.

**Changes**

- Delete migrated legacy selectors, dead components, temporary aliases, and the
  duplicate-root migration allowlist.
- Reduce `main.css` to its documented global responsibilities.
- Make the showcase describe the final atlas system: component purpose,
  production variants, states, accessibility, and provenance. Remove misleading
  M3 Expressive copy and unused giant button specimens.
- Update `docs/frontend_guide.md`, `docs/features-request/frontend.md`, and
  `docs/features-request/prototype_map.md` to match reality.
- Keep historical rationale concise; do not retain dead APIs for compatibility
  when the repository has no caller.

**Tests**

- Static search fails on legacy selectors in production templates/scripts.
- CSS ownership guard has no temporary exceptions.
- Unit, integration, frontend, and E2E suites pass.
- Final screenshot matrix from F21 remains visually stable.

**Acceptance**

- There is one component API and one selector owner for each primitive.
- `main.css` no longer styles common component roots.
- A future engineer can determine where any visual rule belongs from the guide
  and file structure alone.

## Recommended execution order

The dependency order is intentional:

1. **F1** prevents further drift.
2. **F2** fixes the visible document-layout bug before aesthetic work.
3. **F3–F5** establish trustworthy controls.
4. **F6–F8** improve live editing and preferences on those controls.
5. **F9–F11** migrate major product surfaces.
6. **F12** produces the requested creation-card evidence.
7. **F13–F14** proceed only after that visual decision.
8. **F15–F16** rebuild the shell and command search on the settled primitives.
9. **F17–F19** migrate auth/Admin/Settings and complete system feedback.
10. **F20** removes runtime delivery debt after the component APIs stop moving.
11. **F21–F22** verify every route and remove the transition.

Do not combine these into one branch-wide commit. If a ticket reveals a design
choice that screenshots cannot settle mechanically, stop at that ticket's
explicit checkpoint rather than encoding a guess across every page.

## Success criteria for the whole program

- Root GDR reads as one printed-atlas product on desktop and phone.
- M3 contributes anatomy and behavior without imposing round geometry.
- No common/editorial selector collision remains.
- Backlinks occupy the intended desktop aside on every document type.
- State and actions are visibly separate.
- Fields implement real Filled/Outlined anatomy.
- Browser confirmations are gone from ImageEditor and destructive document flows.
- Entity symbols, tints, and account symbol style update immediately.
- Document keyboard navigation follows the settled hybrid model.
- Autosave remains reliable and is still the only persistence mode.
- `Giocatori` is a clear table/dialog workflow.
- Creation lives in the approved collection pattern after the screenshot gate.
- Auth, Admin, Settings, shell, search, and error pages use the same atlas system
  as world content; no placeholder Home remains.
- Phone drawers/dialogs contain focus, restore their opener, and never expose
  background controls to keyboard users.
- Htmx pending and failure states are visible, local, and duplicate-safe.
- Icons render without a global replacement runtime; fonts and screenshots do not
  depend on third-party network availability.
- Base and lazy-editor payload budgets are measured and enforced.
- Every affected page has passing tests, desktop/phone screenshots, prototype
  comparison, implementation documentation, and an isolated commit.
