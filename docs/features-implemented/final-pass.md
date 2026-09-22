# Final responsive and visual pass

F21 evaluates the product as pages rather than as components: every route is
walked at desktop and at 390×844, compared against the prototype, scanned for
accessibility, and driven by keyboard. This document is the audit table, the
fixes it produced, and the findings that are recorded rather than fixed.

## What changed

Four defects, all local or systemic:

1. **The world-overview `quick_strip` landmark was stale.** `seed/prototype_map.yaml`
   mapped it to `.grid--quick`, which no stylesheet or template produces. The
   app renders `<common.Grid min="quick" flush>` → `.grid.grid-auto.grid-flush`.
   The landmark now points at `.grid-flush`; `test_overview_matches_the_prototype_geometry`
   looks at the same class. The landmark now resolves and the compare report
   measures the strip instead of reporting it missing.
2. **The save indicator stole a row of space** (the user's own note, written in
   a character body: *"Il coso sopra che dice salvato si ruba dello spazio"*).
   `common.SaveIndicator` was the first block inside `.container`, so showing
   "Salvato" pushed the masthead, crumbs and document bar down and hiding it
   pulled them back. It now overlays the container's top padding band
   (`position: absolute`, `height: var(--container-pad-top)`), so appearing and
   disappearing never moves the page. Verified: the document bar's document-space
   `y` is identical before and after a save on desktop and phone.
3. **`test_character_form_uses_face_pickers` was racy.** It wrapped the
   `ChoiceGrid` radio clicks in `expect_navigation()`, but the choice now
   auto-saves with a JSON `PATCH` from `ImageEditor.js` — there is no
   navigation, so the test timed out. It now waits for the PATCH response and
   for the editor's "Salvato" status between the two choices, which also stops
   the tint PATCH from racing the version the symbol PATCH writes back.
4. **The 48px World Settings overflow at 412px stayed fixed.** Every route
   reports `scrollWidth - clientWidth == 0` at 390px (and at 1440px).

Plus two accessibility defects found by the axe scan and fixed:

- **`common.ChoiceGrid` radios had no accessible name.** The emoji options got
  one from the visible emoji, but the tint and shape marks are colour / SVG only,
  so the inputs were unnamed (axe `label`, critical). Each input now carries
  `aria-label="{{ option.label }}"`.
- **A non-stacked table's scroll wrapper was not keyboard reachable.**
  `common.Table` with `stack=False` (the Giocatori table, the showcase table)
  keeps its columns and scrolls sideways on a phone, but the wrapper had no
  `tabindex` (axe `scrollable-region-focusable`, serious). It now takes
  `tabindex="0"` and, when a `label` is passed, `role="region"`. Stacked tables
  are unchanged.

## Audit table

Legend: **✓** reviewed and clean, **✎** fixed, **–** recorded, not fixed.

| Page group | Desktop | Phone 390 | Notes |
|---|---|---|---|
| Worlds list | ✓ | ✓ | no overflow, no console/network error |
| Worlds new | ✓ | ✓ | |
| World overview | ✎ | ✎ | `quick_strip` landmark stale → fixed; save-indicator space → fixed; masthead role eyebrow is a structural divergence (see below) |
| World Settings | ✓ | ✓ | 48px overflow confirmed gone; members table scroll region made focusable ✎ |
| Characters list (populated + empty) | ✓ | ✓ | empty state reads "Nessun personaggio: creane uno" |
| Character detail | ✎ | ✎ | ChoiceGrid accessible names ✎; save indicator ✎ |
| NPCs list (populated + empty) | ✓ | ✓ | |
| NPC detail | ✎ | ✎ | ChoiceGrid accessible names ✎ |
| Places atlas (populated + empty) | ✓ | ✓ | |
| Place detail | ✎ | ✎ | shape ChoiceGrid names ✎ |
| Sessions ledger (populated + empty) | ✓ | ✓ | |
| Session detail | ✓ | ✓ | recovery/pager states reviewed |
| Stories list (populated + empty) | ✓ | ✓ | |
| Story detail | ✓ | ✓ | |
| Pages list (populated + empty) | ✓ | ✓ | |
| Page detail | ✓ | ✓ | |
| Account Settings | ✓ | ✓ | no save button; polite feedback |
| Admin users + invitations (populated) | ✓ | ✓ | role/status pills readable; scroll region N/A (stacked) |
| Admin users (empty) | ✓ | ✓ | `Nessun utente` / `Nessun invito` empty states present; a fresh E2E DB has only the bootstrap admin |
| Command palette (loading/results/empty/offline/error) | ✓ | ✓ | covered by `test_request_feedback`; keyboard pass below |
| 404 HTML page | ✓ | ✓ | `harness screenshot --expect-status 404` |
| 403 HTML page | ✓ | ✓ | member on `/admin/users` |
| 500 HTML page | ✓ | ✓ | rendered with a request id; no overflow, no errors |
| Login / registration + validation failure | ✓ | ✓ | native `required` blocks submit; focus lands on the summary |
| Desktop rail / phone drawer, long nav + user data | ✓ | ✓ | drawer: focus trapped, background inert, Escape restores focus |
| Component showcase `/components` | ✓ | ✓ | reviewed; contrast findings recorded below |
| Roles: anonymous / Admin / Master / Player | ✓ | ✓ | Player sees a read-only document (no edit command); Master can edit content; see the settings 403 note |

Wide-desktop reading-measure check: at 1920px the container stays at its
1220px cap and the prose column measures 680px (`--measure: 68ch`), with no
horizontal overflow. The measure does not stretch with the viewport.

## Compare numbers

`uv run harness compare <path> --base-url http://localhost:8002`, before and
after the change. Every mapped page is **identical before and after** — the
fixes are invisible to the pixel diff (the indicator is hidden on a plain load;
the accessible names and the scroll `tabindex` do not paint). The only change is
that `quick_strip` now resolves.

| Page | Desktop before → after | Phone before → after |
|---|---|---|
| Worlds list | 27.77% → 27.77% | 19.69% → 19.69% |
| World overview | 17.76% → 17.76% | 17.56% → 17.56% |
| Characters list | 47.36% → 47.36% | 55.90% → 55.90% |
| Character detail | 20.22% → 20.22% | 30.58% → 30.58% |
| NPCs list | 46.06% → 46.06% | 53.68% → 53.68% |
| Places atlas | 30.40% → 30.40% | 40.05% → 40.05% |
| Place detail | 25.87% → 25.87% | 40.61% → 40.61% |
| Sessions ledger | 9.47% → 9.47% | 15.46% → 15.46% |
| Session detail | 23.23% → 23.23% | 23.26% → 23.26% |
| Stories list | 31.54% → 31.54% | 33.65% → 33.65% |
| Story detail | 17.75% → 17.75% | 29.45% → 29.45% |
| Pages list | 8.55% → 8.55% | 14.13% → 14.13% |
| Page detail | 16.61% → 16.61% | 22.02% → 22.02% |

The absolute percentages are data and font-rendering differences against the
prototype, not defects; the signal is that none of them moved. The world
overview now also reports `quick_strip.y differs by 29px (app below prototype)`:
the app renders the world role as an `.eyebrow` above the title, the prototype
puts it in the aside. That is a settled layout difference from an earlier
ticket, not a regression, and the pixel diff is unchanged.

## Accessibility

`tests/e2e/test_accessibility.py` runs axe-core (a dev dependency) over the
world overview, a character detail, World Settings, Admin, the showcase, Login,
registration and the 404 page, at both viewports. It fails on any serious or
critical finding **except** `color-contrast`, which is reviewed below.

Fixed (see above): `label` (critical, ChoiceGrid) and
`scrollable-region-focusable` (serious, Table wrapper).

### Accepted: colour contrast

The scan reports `color-contrast` (serious) on the identity palette. These are
the settled atlas colours, reproduced from `prototypes/devin-prototype/`
(mentions, the quick strip's foot, the story band, the avatar initials), plus
the app's own M3 status/role aliases. Correcting them means changing the
palette, which is a design decision, not a cleanup, so they are recorded here:

| Surface | Ratio | Where |
|---|---|---|
| Character/place mentions (tint as text) | 1.81 – 3.58 | character, NPC, session, page bodies |
| Quick-strip foot labels | 2.50 – 3.75 | world overview |
| Story band (`surface` on ochre) | 2.18 | stories |
| Avatar initials on `--cat-*` | 3.05 – 4.41 | showcase, members |
| Status/role pills (`--status-*`/`--role-*` on `-bg`) | 3.16 – 4.34 | Admin, World Settings, showcase |
| Session pager, disabled direction | 1.84 | session detail |
| Login eyebrow / cover foot | 4.34 | login, registration |

The pager case is an inactive control (WCAG 1.4.3 exempts inactive UI); it is
flagged because it is a `<span>`. The rest are near-misses or a palette that
needs a text-safe variant of each tint. A future palette ticket can close them;
`final-pass.md` is the record of why they are left.

## Keyboard journeys

Keyboard-only, no pointer:

| Journey | Result |
|---|---|
| Shell / phone drawer: open, focus trapped inside, Tab stays in the rail, Escape closes and restores the opener | pass |
| Command search: `Ctrl+K`, type, `ArrowDown`, `Enter` navigates, `Esc` closes | pass |
| Authentication: Tab email → password → submit, native `required` blocks the empty submit | pass |
| Collection creation: focus the create card, `Enter`, name, `Enter` | pass |
| Document editing: focus the body block, `Enter`, type, `Ctrl+Enter` | pass |
| Image history: focus the trigger, `Enter`, focus enters the dialog, `Esc` closes | pass |
| Admin invitation: focus "Invita utente", `Enter`, focus enters the dialog | pass |
| World-player invitation: focus the add button, `Enter`, focus enters the dialog | pass |

One platform note: `Ctrl+Enter` closes the editor on desktop but not under the
Pixel 7 emulation, where CodeMirror's Android input handling swallows the
chord; `Escape` closes it there and the editor's own controls do the same work.
A physical Ctrl key does not exist on the phone, so this is not a user-facing
defect.

## Limits / recorded, not fixed

- **World Settings is owner-only; a non-owner Master sees the "Impostazioni"
  command on the overview and gets the designed 403.** The overview always
  renders the command; the page requires `owner_world`. Deciding whether a
  Master should manage settings is a permission-model decision, out of a
  visual pass.
- **The masthead role eyebrow** (app: eyebrow above the title; prototype:
  eyebrow in the aside) is a settled layout difference, not a regression.
- **Colour contrast** above.

## How to reproduce

```bash
uv run harness compare /worlds/<id> --base-url http://localhost:8002
uv run harness test unit        # hooks, conventions, payload budget
uv run harness test frontend    # component contracts
uv run harness env up --mode local && uv run harness test integration
uv run harness env up --mode docker && uv run harness test e2e --fresh
```
