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
- **Drawing.** Triangles, rectangles, circles and point-placed polygons are
  created by dragging (or, for a polygon, clicking each vertex and pressing
  Enter); the line tool creates a straight open path. A shape is selected by
  clicking it or its layer, moved by dragging, scaled by a corner handle and
  rotated by the handle above the selection. `Ctrl`/`Cmd`+`D` duplicates,
  `Del` deletes, the arrow keys nudge, and the inspector reorders the object.
- **Styling.** A twelve-colour palette plus a custom fill and stroke colour,
  stroke width, opacity, and independent "no fill"/"no stroke" switches.
- **Vertex editing.** The `Vertici` mode shows a handle per vertex and a toggle
  per edge. Clicking an edge inserts a vertex on it; dragging a handle moves the
  vertex; `Alt`+click removes one (never below three); the midpoint toggle hides
  that edge's outline while the fill stays closed, which is how adjoining body
  parts avoid a black seam. A move snaps to the grid and to the polygon's other
  vertices within a screen-space tolerance, with a visible marker; `Alt`
  bypasses the snap.
- **Undo/redo.** `Ctrl`/`Cmd`+`Z` and `Ctrl`/`Cmd`+`Shift`+`Z`, or the toolbar
  buttons. One completed drag is one step; panning, zooming and selection are
  not steps.
- **Layers.** The object list is rebuilt from the document on every change; a
  layer can be hidden (it disappears from the artboard but stays in the list)
  and selecting a row selects the shape.
- **Straight cut.** The `Taglia` tool takes two points on the polygon's
  boundary (clicking an edge inserts the vertex there), previews the chord and
  splits the shape. The chord must stay inside and yield two valid polygons, so
  adjacent vertices, coincident points and chords that leave the shape are
  refused with a message. The piece that kept the original id stays selected,
  the new piece sits right after it, and the shared cut edge starts hidden so
  the silhouette is unchanged. The whole cut is one undo step.
- **Grouping.** `Shift`+click selects several shapes; `Raggruppa` nests them
  into one group, which the layer list shows indented. The group takes an
  identity transform, so grouping never moves anything, and moving, scaling or
  rotating the group moves its children with it (a click inside a selected
  group drags the group, not the child under it). `Separa` dissolves the group,
  composing each child's transform with the group's so nothing moves. The
  format's nesting limit is enforced with a message. Objects can be renamed.
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
- **The client is a small module set** in `src/frontend/js/drawings/`:
  `geometry.js` (affine matrices, polygon tests, bounds), `scene.js` (document
  operations and the undo history), `render.js` (the SVG projection of the
  document plus the selection overlay), `controller.js` (tools, pointer and
  keyboard interaction, styles, the save lifecycle) and `index.js` (the entry).
  It is bundled by esbuild into `static/js/drawings.js` and loaded on demand by
  `editorial/DrawingEditor.js`, so a reading page never downloads it.
- The renderer is a pure projection: the scene layer carries the viewport
  transform, and the overlay is drawn in artboard coordinates with the transform
  applied, so a handle keeps its size while zooming. A hidden polygon edge is
  rendered as contiguous outline runs, so the fill stays closed.
- `editorial/DrawingEditor.jinja` renders the workspace from a `SceneDocument`
  and embeds it as JSON; the server-rendered shapes are the no-JS first paint
  and the controller replaces them on mount.
- `editorial/DrawingEditor.css` owns the three-column composition. The two fixed
  rails, the artboard proportion, the swatch and the layer checkbox are role
  tokens in `main.css`.
- `prototypes/devin-prototype/drawings.html` and `drawing-editor.html` are the
  static visual reference, with `drawing.css` mirroring the component's classes.
  `seed/prototype_map.yaml` maps `/drawings` and `/drawings/<id>` to them.
- The tool icons are server-rendered from the registry; the new names were added
  to `tools/build_icons.mjs` and generated with `npm run icons`.
- The algorithms are covered by pure tests under `tests/js/`, run with Node's
  built-in test runner (`npm run test:drawings`).

## Used by

- `pages.drawings.DrawingList` and `pages.drawings.DrawingDetail`.
- `pages.showcase.Showcase` — a read-only specimen.

## Limits

- **Bézier curves are not here yet** (`T08`); the `Linea` tool draws a straight
  open path.
- A cut splits along a straight chord only; a curved cut is not offered. The
  two pieces are independent afterwards — the shared boundary is not welded.
- A group is only as deep as the format allows, and only siblings can be
  grouped; nodes at different levels are refused with a message.
- Snapping covers the grid and a polygon's own vertices; edge midpoints,
  attachment points and other objects are not snap targets yet.
- Scaling keeps the dragged corner proportional-ish but does not snap to a
  ratio; rotation has no angle snapping.
- Pan/zoom exists (wheel to zoom, `Space`+drag or the middle button to pan) but
  there is no "fit" control and no zoom readout.
- The layer list is a flat outline of the tree (one indented row per node); it
  is not a collapsible tree yet.
- Phone is a preview, not a drawing surface.
