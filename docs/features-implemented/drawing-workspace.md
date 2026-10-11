# Drawing workspace

An admin-only **Disegni** area for authoring editable geometric illustrations.
It delivers the first workspace milestone of REQ-0015, not the later asset
library, skeleton, publishing or export capabilities.

## What it does

- `/drawings` lists saved drawings in pages of 24; create a blank drawing,
  rename it in the workspace and save explicitly with **Salva** or Ctrl/Cmd+S.
- Drag triangles, rectangles and ellipses onto the artboard. Click polygon
  vertices and double-click or press Enter to finish. Drag open lines or cubic
  Bézier curves.
- Select through the canvas or connected scene tree; Shift selects multiple
  objects. Groups expand/collapse, eye controls on the right toggle visibility,
  and arrow/Home/End keys navigate the tree without nudging artwork.
  The **Genitore** selector attaches an object to a group or the scene root
  while preserving its world placement; cycles and excessive nesting are refused.
  Move, scale, rotate, duplicate, delete and reorder objects. Arrow keys nudge.
- **Vertici** edits polygon vertices or path endpoints/control handles. Click a
  polygon edge to insert a point; Alt-click a vertex to remove it (minimum
  three). Click a straight path segment to insert an editable polyline point.
- Polygon edge-midpoint controls hide individual outlines without losing fill.
  **Taglia** selects two boundary points and splits along an internal straight
  chord. Pieces edit independently; their new shared outlines start hidden.
  Escape cancels a pending cut, including temporary inserted boundary points.
- **Raggruppa** combines consecutive sibling objects; **Separa** composes the
  parent transform into the children. Nested child edits use the complete
  parent transform. Hidden groups are excluded from canvas selection.
- A curated fourteen-colour palette, including pure white and black, custom
  fill/stroke colours, width and opacity
  support angular silhouettes and faint details. For paths, palette choices
  change the stroke colour.
- A floating selection bar keeps vertex/group/order actions and independent
  grid visibility, grid snap and geometry snap controls together. Moving an
  object or group snaps its anchor, excluding the selected objects themselves.
  Vertices, polygon midpoints and path endpoints are geometry targets;
  Alt bypasses snapping. Hiding the grid does not change snap preferences. Wheel zooms;
  Space-drag or the middle mouse button pans.
- Undo/redo is in-memory and bounded to 60 completed operations. A drag or
  property change is one step; view changes and selection are excluded.
- A stale save returns 409 and retains local work. **Salva come copia** creates
  a separate document; **Ricarica** asks before discarding local edits. Edits
  made during a normal save remain dirty after its earlier snapshot succeeds.
  Unloading a dirty editor prompts before leaving.
- Phone displays the complete artwork with editing controls disabled. Authoring
  targets mouse and keyboard.

## How it is built

- `src/backend/drawings/` owns models, validation, services, JSON routes and HTML
  views. The JSON API is `/api/drawings/`; every route and service enforces the
  site-admin boundary. Summaries select metadata and a database object count,
  without loading every scene into the list.
- Alembic creates a `drawings` table with creator, timestamps, optimistic version
  and a JSONB native document. A feature-local `SceneJSON` adapter keeps the
  model attribute typed as `SceneDocument`; a save replaces the complete value.
- Format version 1 stores an artboard and ordered polygon/ellipse/path/group
  nodes with stable node IDs, names, affine transforms, styles and visibility.
  Polygon vertices are ordered coordinate pairs; edge visibility follows each
  outgoing edge. Paths use absolute M/L/C/Z commands. UI selection, viewport,
  handles and guides are not saved as artwork.
- Validation rejects unknown fields/versions, duplicate IDs, malformed paths,
  non-finite/singular transforms and self-intersecting/zero-area polygons.
  Limits are 2,000 nodes, eight nested group levels, 256 points per polygon,
  512 commands/8,000 characters per path, and a 1 MiB native document.
- Native format version and database update version are distinct. Updates
  require the version read by the client; SQLAlchemy and the transaction
  dependency detect simultaneous writers and return 409.
- JinjaX supplies the shell, controls and safely escaped scene JSON. The lazy
  esbuild bundle has geometry, scene/history, SVG rendering and controller
  modules under `src/frontend/js/drawings/`. SVG elements are created through
  namespaced DOM APIs. The renderer composes parent matrices for child handles
  and renders partial polygon outlines as contiguous runs.
- UI styling belongs to `editorial/DrawingEditor.css`; role tokens live in
  `main.css`. `drawing-editor.html` and `drawings.html` are the static visual
  references mapped by `seed/prototype_map.yaml`.

## Used by

`pages.drawings.DrawingList`, `pages.drawings.DrawingDetail`, and a read-only
specimen in the component showcase.

## Limits

- No linked scenes/libraries, anchors, skeletons, portrait/document publishing,
  PNG/SVG downloads, card printing, animation, imports or clipping.
- Explicit saving only: no autosave, offline/crash recovery or persisted undo.
  A failed/ambiguous response does not claim successful persistence; inspect or
  reload server state before treating local work as durable.
- Ellipses remain ellipses, cuts are straight, boundaries are not welded, and
  polyline/cubic editing does not offer a full path-boolean toolset.
- Groups must be consecutive siblings to preserve overlap order. The layer list
  is a connected, collapsible scene tree. Group styling is not exposed.
- No angle/aspect-ratio snapping or zoom readout/fit control. Numeric coordinate
  authoring and stable vertex IDs for future linked-asset overrides are deferred.
- JavaScript is required for complete interactive rendering, including groups;
  the server-rendered first paint is not a complete no-JavaScript renderer.
