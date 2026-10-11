# Drawing workspace

The drawing editor's workspace and its persistence, opened by
`REQ-0015/T01`. An admin-only area stores geometric artwork as a native, typed
document; the drawing tools themselves arrive in later tickets.

## What it does

- **Disegni** is an admin-only area in the global navigation: a ledger of saved
  drawings (name, object count, last update), a command to create a blank one,
  and the editor that reopens a stored document.
- `editorial.DrawingEditor` composes the whole workspace: a tool rail on the
  left, the artboard in the middle, layers and properties on the right.
- The tool rail names every tool the editor will offer (select, triangle,
  rectangle, circle, polygon, line, cut) and shows the active one with a pressed
  state, not only a colour.
- The artboard is a real SVG: a faint grid, the scene's shapes and the vertex
  handles of the selected object. Shapes render from typed scene data, not from
  raw SVG strings.
- **Explicit save.** The Save button and `Ctrl`/`Cmd`+`S` send the whole
  document with the version it was read at. The page's save indicator reports
  dirty, saving and saved; a failed save says so and never claims success; a
  conflicting save (HTTP 409) is reported and the local document is kept.
  Unsaved changes warn on unload.
- Below the phone breakpoint the workspace stacks, the tools scroll
  horizontally, and the canvas becomes a preview with a note that drawing needs
  a computer.

## How it is built

- `src/backend/drawings/` is a self-contained feature: `models.py` (one
  `drawings` table with a JSONB `document`), `schemas.py` (the native document
  and the transport schemas), `service.py`, `routes.py` (JSON API under
  `/api/drawings`) and `views.py` (the HTML pages under `/drawings`).
- The native document is an ordered tree of `polygon`, `ellipse`, `path` and
  `group` nodes with stable ids, local affine transforms and styles, plus the
  artboard. Every value is validated on the way in: format version, shape tags,
  numbers, matrices, colours and geometry. Unknown fields and unknown versions
  are rejected rather than dropped, so a document written by a future version
  cannot silently lose data.
- The whole document is replaced on save, because a nested mutation is invisible
  to SQLAlchemy. `expected_version` is **required** on an update: a drawing is
  written as one value, so a missing precondition would silently overwrite
  another session's work. The row's `version` is the optimistic lock and is
  unrelated to the document's own `schema_version`.
- Authoring is admin-only in the dependency *and* in the service, so a guessed
  drawing id cannot bypass it.
- `editorial/DrawingEditor.jinja` renders the workspace from a `SceneDocument`
  and embeds it as JSON for the client. `editorial/DrawingEditor.js` keeps the
  last acknowledged value and version, sends the document on an explicit save,
  and reports dirty/failed/conflict states through the page's save indicator.
- `editorial/DrawingEditor.css` owns the three-column composition. The two fixed
  rails and the artboard proportion are role tokens in `main.css`
  (`--drawing-tool-rail`, `--drawing-side-rail`, `--drawing-artboard-ratio`,
  `--drawing-swatch`, `--drawing-layer-check`).
- `prototypes/devin-prototype/drawings.html` and `drawing-editor.html` are the
  static visual reference, with `drawing.css` mirroring the component's classes.
  `seed/prototype_map.yaml` maps `/drawings` and `/drawings/<id>` to them.
- The tool icons are server-rendered from the registry; the new names were added
  to `tools/build_icons.mjs` and generated with `npm run icons`.

## Used by

- `pages.drawings.DrawingList` and `pages.drawings.DrawingDetail`.
- `pages.showcase.Showcase` — a read-only specimen.

## Limits

- **No drawing interaction yet.** The component renders a stored scene and saves
  it; the tool buttons and commands are inert until the next tickets. A save
  with no edits is a no-op.
- The scene value is validated but not yet exercised by real editing: the tool
  tests, vertex editing, splitting, grouping and curves arrive in later tickets.
- Only the first object is the selection; there is no selection UI beyond the
  layer list yet.
- The prototype's tool glyphs are text characters; the application renders the
  Lucide registry icons instead.
- Phone is a preview, not a drawing surface.
