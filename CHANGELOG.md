# Changelog

All notable changes to Root GDR are documented in this file. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); the version in
`pyproject.toml` is authoritative and is chosen by Oscar at release time.

Unreleased notes live as fragments in [`changelog.d/`](changelog.d/), one per
significant change, named after the ticket that made it. Render them without
consuming anything:

```console
uv run towncrier build --draft --version UNRELEASED
```

<!-- towncrier release notes start -->

## 0.2.0 — 2026-10-12

### Added

- Add `editorial.TintPicker`: a compact tint control with a swatch-and-name trigger, the twelve-tint radio palette in a popover, a ring-and-check selected mark, viewport bounds, 44px phone targets and a disabled state. (REQ-0008-T01)
- Add `editorial.DocDetails`: a reachable summary trigger and a native-dialog panel — right-side sheet on desktop, full screen on phone — that opens only from its trigger, returns focus on close and leaves the body, editor state and URL untouched; `common.Dialog` gains the manual opt-out for pre-rendered dialogs. (REQ-0010-T01)
- Add manually invoked, loopback-only Vikunja deployment with a dedicated owner and scoped tooling bot, private credentials, persistent user-systemd lifecycle, conservative idempotence and coordinated encrypted recovery. Existing board demonstrations remain untouched. (REQ-0012-T01)
- Add GitHub Actions CI: four jobs (checks and unit tests, frontend component tests, integration, end-to-end) on a clean frozen-lockfile checkout, with SHA-pinned actions, read-only permissions, no secrets and no deployment, and a failure-only diagnostic bundle collected by `tools/ci/collect_artifacts.py` (allowlisted, redacted, size-capped). (REQ-0001-T02)
- Add page-level document shortcuts: F2 opens the body when no block is focused, Ctrl/Command+Shift+Enter runs the current publication command through the persistence barrier, the bar advertises both with `aria-keyshortcuts`, and an Italian `Scorciatoie` entry in the `Altre azioni` menu lists them. (REQ-0006-T02)
- Add an atlas calendar beside the native date field: a desktop popover with month navigation, `Oggi` and `Cancella`, roving keyboard focus and a leap-day-safe local calendar, while a phone keeps the platform picker and the native input stays the canonical value. (REQ-0007-T02)
- Report a story's composed sessions as a read-only reference list, validated like the sessions list: duplicates, another world and unseen drafts are refused with a typed 422, a reader never learns a draft's title, and the update/version/lock contracts stay unchanged. (REQ-0010-T02)
- Validate request documents offline with `harness backlog check-requests`: typed frontmatter, unique IDs, resolving links and retained `H1`–`H7`/`F1`–`F22` aliases, with the historical documents catalogued without import. (REQ-0012-T02)
- Add a report panel: a floating dialog that keeps a draft description on the backend and attaches the visible screenshot, the full-page screenshot and the page HTML, recoverable after a reload. (REQ-0014-T02)
- Add `harness backlog` for typed API v2 reads and ticket creation over a loopback tunnel, with full pagination, bounded errors and a scoped token that never appears in arguments or output. (REQ-0012-T03)
- Annotate a report screenshot before submitting it: coloured arrows, boxes and text plus an optional blur, saved back over the capture it marks. (REQ-0014-T03)
- Drawings are stored as a native, typed document in PostgreSQL and saved
  explicitly. An admin-only **Disegni** area lists the drawings, creates a blank
  one, and opens it in the workspace; a save sends the whole document with the
  version it was read at, and a conflicting save is refused instead of overwriting
  another session's work. (REQ-0015-T03)
- Add coordinated PostgreSQL/uploads and SQLite/attachments backups with typed,
  checksummed recovery manifests, verified restic encryption on the controller,
  and isolated restore that refuses existing or production targets. Backup failures
  resume the unchanged build and block migrations; production data is never
  restored automatically. Weekly timer activation and retention remain separate. (REQ-0001-T04)
- Move, close, reopen and comment on tickets through `harness backlog`: placement is read before a write, close follows the view's done bucket, and marker comments stay idempotent across retries. (REQ-0012-T04)
- Record a reproduction for one report: the panel keeps the browser steps and the backend calls of that report, joined by a cookie so ordinary navigation stays recorded, each backend step naming the request and trace it belongs to. (REQ-0014-T04)
- The drawing workspace now draws. Triangles, rectangles, circles and
  point-placed polygons are created on the artboard, selected, moved, scaled,
  rotated, duplicated, reordered and deleted; a curated palette plus colour,
  width and opacity controls style them; and undo/redo covers every completed
  gesture. The object list is rebuilt from the document and a layer can be
  hidden without losing its geometry. (REQ-0015-T04)
- Import the cycle's plan tickets with `harness backlog import`: dry-run writes nothing, a second import creates no duplicates and preserves manual progress, and every card links its request document and plan section. (REQ-0012-T05)
- Submit a report to the board from the panel: one ticket with the description, the annotated captures and a bounded diagnostics document, created once and never twice for the same report. (REQ-0014-T05)
- A polygon is now edited at its vertices: a click on an edge inserts a point,
  dragging a handle moves one, `Alt`+click removes one, and each edge has a
  toggle that hides its outline without losing the fill. Moves snap to the grid
  and to sibling vertices, with a visible marker, and `Alt` bypasses the snap. (REQ-0015-T05)
- Add manual, namespaced Ansible rollout with immutable verified image transfer,
  private pinned tooling, capacity/listener/configuration preflight, a coordinated
  encrypted backup gate, separate one-shot migrations and real authenticated
  production verification. Healthy unchanged reapply is a no-op; application
  rollback is attempted once only for identical verified schema heads. Unsafe or
  failed recovery stops writers for operator review, without database restore or
  downgrade. Read-only helper access preserves upload volume ownership. (REQ-0001-T06)
- Add pinned Towncrier release-note fragments in `changelog.d/` with a draft that writes nothing, and keep `pyproject.toml` as the single application version. (REQ-0012-T06)
- A polygon can be cut in two: the `Taglia` tool takes two boundary points
  (inserting a vertex when a click lands on an edge), previews the chord and
  splits the shape. The chord must stay inside and produce two valid polygons;
  the original keeps its id and the new piece sits right after it. The shared
  cut edge starts hidden so the silhouette is unchanged, and the whole cut is
  one undo step. (REQ-0015-T06)
- Seed the committed reference world once during the first production bootstrap, through a tested backend entrypoint that preserves any existing account and world on later rollouts. (REQ-0001-T07)
- Objects can be grouped. `Shift`+click selects several shapes, `Raggruppa`
  nests them into one group (the layer list shows the nesting), and the group
  moves, scales and rotates as a unit; `Separa` dissolves it, composing each
  child's transform so nothing moves. Objects can be renamed, and a click inside
  a selected group moves the group rather than the child under it. (REQ-0015-T07)
- Run the encrypted off-server backup weekly from the PC on Sunday 10:00 Europe/Rome, keeping four complete copies per application with overdue and failure visibility. (REQ-0001-T08)
- Add verified Vikunja attachment uploads and metadata listing to the Backlog CLI,
  with identical-file reuse, ambiguous-write read-back and partial-batch receipts.
  Attachment permissions require a separately approved scoped token; existing
  credentials are never rotated automatically. (REQ-0012-T08)
- Draw open lines, editable polylines and cubic Bézier details in the admin-only drawing workspace. Endpoint/control handles, palette stroke colours and opacity retain their editable state after reopening. Complete the workspace with drawing names, safe conflict copies, bounded metadata-only lists, corrected nested-group transforms, cancelled-gesture recovery and a phone-only preview. Native documents reject malformed paths, invalid geometry and non-finite transforms; scene JSON and labels render safely as text. (REQ-0015-T08)
- Add a shared four-type/six-area backlog label catalogue, verified label/task-colour CLI operations, and consistent classification in the bug and feature intake skills while preserving human metadata and reporting partial failures. (REQ-0012-T09)
- Mark a request's implementation tickets with a `req:NNNN` label in its own cool colour, and relate them to the request as real board relations instead of a comment. (REQ-0012-T10)
- Add pure white and black to the drawing palette for both filled shapes and open-path strokes. Keep all fourteen swatches in two compact rows. (REQ-0015-T10)
- Build private deployment image artifacts from an explicitly selected Git commit,
  independent of local edits, with verified revision/version/architecture and a typed
  immutable image ID, archive size and checksum manifest. Dry-run builds nothing;
  artifact validation detects missing, linked or corrupted transfer inputs. (REQ-0001-T11)
- Add the opt-in `/implement-ticket` skill: resolve a real Vikunja task and prerequisites, use its discovered workflow, and require verified persistence/tests/evidence and a local commit before completion. Preserve manual progress and report blocked credentials/relations without changing permissions or executing an entire epic implicitly. (REQ-0012-T11)
- Keep selection actions in a floating toolbar and independently toggle grid visibility, grid snapping and geometry snapping. Whole-object and group movement now snaps to the grid or other geometry without snapping back to the selected objects themselves; Alt temporarily bypasses snapping. (REQ-0015-T11)

### Changed

- Make the document bar's commands icon-only with Italian labels and tooltips that name the current action, move the destructive commands into a labelled `Altre azioni` menu, keep the facts readable and the phone targets at 44px, and let the tooltip yield to an open menu. (REQ-0005-T01)
- Make document commands wait for pending saves: publication and lock drain the in-flight write and the dirty queue through a `settle()` promise, cancel on a failed, conflicting or offline save while keeping the recovery panel, and run once per click. (REQ-0006-T01)
- Start a new session's real date at the creating browser's own calendar date: the trigger sends the local ISO date, the route persists it before the redirect, and an absent value falls back to today in Europe/Rome instead of the server's UTC date. (REQ-0007-T01)
- Feed the `@` menu from bounded, policy-filtered queries: mention suggestions carry the stored `animal`/`shape` mark tokens as data, hide other authors' drafts and other worlds exactly like the list services, and cap each type instead of loading every match. (REQ-0009-T01)
- Harness test commands accept suite-local file/node selectors and bounded pytest
  arguments after `--`, preserve quoted filters and exit codes, and keep fresh E2E
  resets separate from integration and user environments. (REQ-0011-T01)
- Replace the document bar's publication pill with `editorial.PublicationStatus`: a compact rectangular stamp on paper whose state colour sits on the rule and a square marker (forest for published, ochre for draft) while the word stays readable ink and always present. (REQ-0005-T02)
- Wire the tint picker into the metadata panels: `editorial.Metadata` renders `kind="tint"` with one hidden field for the autosave, a choice previews immediately and persists as the canonical value, and an applied value (a restored draft) repaints the control. (REQ-0008-T02)
- Give the `@` menu a fixed rectangular mark — the stored animal, the place shape or the kind cue, tinted by the document — with long names ellipsizing, hostile names staying text, and the arrow/Enter selection unchanged. (REQ-0009-T02)
- Gate landmark mappings with `harness compare --check-landmarks`: a missing, ambiguous or unexpectedly hidden landmark fails with its route, viewport, landmark, side and selector, `optional_on`/`hidden_on` viewports handle by-design cases like the closed phone rail, and geometry stays diagnostic. (REQ-0011-T02)
- Production images exclude local data and development artifacts, run without
  migration credentials, and retain uploads outside the read-only application
  filesystem. Database initialization and schema upgrades use separate credentials. (REQ-0001-T03)
- Move a story's period, progress, tint and session selection into the details panel behind one summary line, with a searchable group of native session checkboxes that keeps chosen sessions visible and writes one hidden field; drop the duplicated inline progress band from the story page. (REQ-0010-T03)
- Record the frontend suite's load-dependent entity-card flake in a known-failure register with its reproduction and evidence, without skips, xfail or a memorized expected total. (REQ-0011-T03)
- Move a page's address, menu position and tint into the details panel and swap the canonical URL from the server's acknowledgement with `history.replaceState` and targeted link updates instead of a navigation, so a pending body, the editor caret and the history survive; a refused slug stays in the panel. (REQ-0010-T04)
- Settle captures and comparisons before the shot: fonts, layout and finite animations finish within a bounded deadline that perpetual animations or stalled requests cannot exceed, `--settle` tunes it, and `--phone-profile phone390` exposes the 390×844 evidence profile. (REQ-0011-T04)
- Deployments can check database/schema/storage readiness and the running build,
  then verify real password login and authenticated reads. Development login and
  showcase endpoints are absent from production. Password-token refresh now accepts
  the application's UUID user identifiers. (REQ-0001-T05)
- Run the existing payload-budget check in pre-commit when assets, editor sources or the bundle, the icon registry or the budget definition change, so a heavy asset fails at commit time without a second set of thresholds. (REQ-0011-T05)
- Keep one Playwright browser location for the harness and direct frontend pytest: `harness browsers` verifies the required Chromium revision and binary, respects an explicit `PLAYWRIGHT_BROWSERS_PATH`, distinguishes missing OS libraries from a missing browser, and `setup.sh` uses it instead of `playwright install`. (REQ-0011-T06)
- Activate the new isolated Root GDR and Vikunja stacks on the home server from a verified commit, with a coordinated encrypted pre-deploy backup, real password logins and the reference world seeded once. Add a separate owner-run Ansible setup for the LAN-only firewall rule, with interactive sudo, read-only check mode and idempotent runtime/permanent application. (REQ-0001-T07)
- Add Ruff 0.15.1 to the development dependencies so `uv run ruff check` and `uv run ruff format --check` match the pre-commit hooks before a commit. (REQ-0011-T07)
- Add LAN-only Vikunja access to the owner-run server setup, with idempotent firewall rules, a verified encrypted backup before changing the existing board listener/frontend URL, and networking rollback that preserves accounts, tickets and attachments. (REQ-0012-T07)
- Install the locked Node dependencies with `npm ci` in `setup.sh --harness` (axe-core for the accessibility scan), resolve the repository from the script's own path so setup works from any directory, and keep the scan failing instead of skipping when axe is missing. (REQ-0011-T08)
- Add a `flag:open-questions` label to the shared catalogue and let intake classification attach it to tickets whose specification still has unresolved questions. A flag marks a condition of the ticket, never a type or an area, and never carries the task colour. (REQ-0012-T09)
- Present drawing objects as a connected, collapsible scene tree rather than separate cards. Move visibility to right-hand eye buttons, preserve focus during tree updates, and support keyboard navigation. Attach objects to local parent groups through the parent selector without moving their artwork; prevent hierarchy cycles and excessive depth. (REQ-0015-T12)

### Fixed

- Center the outlined field's floating label on the visible rule: the notch height is explicit and the outline shifts up by half of it, so the rule lands on the box edge where the label sits, instead of half a notch below it. (REQ-0002-T01)
- Make an empty document body a real writing target on all six types: a minimum height, a CSS-drawn invitation in the document's own voice, and the same open commands, while readers and locked documents stay read-only and the copy never enters the Markdown source or the API. (REQ-0003-T01)
- Center the autosave dot on the status text's line instead of the whole padding band, and let a wrapped long message grow the indicator downward so it never climbs over the topbar or moves the crumbs and the document bar. (REQ-0004-T01)
- Recreating a Docker test environment no longer recreates its database a second
  time after preparation, so both integration and E2E schemas remain available. (REQ-0011-T09)
- Finish polygons on a double-click without adding the closing point twice. Invalid crossing outlines retain their draft and report the actual geometry problem. (REQ-0015-T09)
- Cached local image builds retain their selected commit in both the OCI revision
  label and runtime build information instead of inheriting another build's value. (REQ-0001-T10)
- A fresh checkout can start the development stack from `.env.example` alone: the template declares the showcase database and the auth settings the app and hooks require. (REQ-0011-T10)
- Expose both Bézier endpoints and their control handles as labelled, focusable editing targets. Tether the second control to the final endpoint rather than the beginning; highlight the active point and support independent keyboard nudging without moving the whole curve. (REQ-0015-T13)
- Keep the read-only scene-tree specimen accessible with valid tree-item semantics, including when the interactive controller is not mounted. (REQ-0015-T14)
