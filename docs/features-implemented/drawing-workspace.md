# Drawing workspace

An admin-only **Disegni** area for authoring editable geometric illustrations.
It delivers the first workspace milestone of REQ-0015, not the later asset
library, skeleton, publishing or export capabilities.

## What it does

- `/drawings` lists saved drawings in pages of 24; create a blank drawing,
  rename it in the workspace and save explicitly with **Salva** or Ctrl/Cmd+S.
  Global Ctrl/Cmd+K search finds the drawing area, permitted creation and drawings
  by title. A typed feature registry supplies both global navigation and search
  destinations, including admin/development visibility. Search filters before a
  metadata-only SQL union, then returns stable 12-result pages with total/count;
  **Altri risultati** loads more. Existing world/content permissions stay enforced.
  Creation is an explicit POST; unconfirmed failures do not offer a blind retry.
  Navigating from dirty artwork retains the existing leave warning.
- Drag locked triangles/rectangles onto the artboard. The triangle split button
  keeps isosceles as its primary action; its menu offers equilateral and right
  triangles with the right angle on either side. Rectangle offers square; polygon
  offers a locked regular preset with 3–32 sides (default six). Submenu choices
  select a tool, not an object; creation remains a bounding-rectangle drag.
  Direct preset edits retain the invariant; equilateral/regular vertices scale
  radially, isosceles retains its centred apex, rectangles keep right angles.
  Topology edits/cuts require explicit unlocking. Existing free artwork stays free.
  The circle button creates a locked circle fitted inside the drag rectangle;
  its submenu creates a free ellipse. Circle editing exposes centre and radius;
  ellipse editing exposes centre and two axes, through handles and numeric local
  document-unit fields. Keyboard handles nudge parameters; invalid radii are refused.
  Incompatible non-uniform own/parent/multi-selection transforms are refused
  atomically with feedback. Explicit unlocking retains appearance and permits
  oval deformation; legacy shapes are not relocked from their names. Click polygon
  vertices and double-click or press Enter to finish. Drag open lines or cubic
  Bézier curves.
- Select through the canvas or connected scene tree; Shift selects multiple
  objects. Groups expand/collapse, eye controls on the right toggle visibility,
  and arrow/Home/End keys navigate the tree without nudging artwork.
  The **Genitore** selector attaches an object to a group or the scene root
  while preserving its world placement; cycles and excessive nesting are refused.
  Move, scale, rotate, duplicate, delete and reorder objects. Arrow keys nudge.
  Delete removes only selected subscenes and their descendants, as one undo step;
  it does not delete the saved drawing. Removed tree-row focus returns to the
  canvas so Ctrl/Cmd+Z still works. Vertical arrows move forward/backward and
  **Primo piano/Sfondo** reach the sibling-order extremes.
  Diagnostics distinguish no selection, own/parent visibility, zero opacity,
  disabled fill/outline and intentionally empty groups. Unpainted/transparent
  content cannot intercept canvas selection; the tree still exposes it. No
  geometry is repaired and no empty group is automatically removed.
- The floating bar exposes **Seleziona**, **Modifica forma** and **Trasforma**.
  A single shape defaults to direct geometry editing after creation/selection;
  groups and multiple selections use whole-selection controls. **T** enters
  Transform with focus in the workspace; Ctrl+T remains the browser shortcut.
  Ellipses expose centre/two-axis handles; locked circles have centre/radius handles. A multi-object transform is one undo
  step. Toolbar and keyboard actions share their availability checks.
- **Modifica forma** edits polygon vertices or path endpoints/control handles. Double-click a
  polygon edge (away from its outline controls) to insert a point; Alt-click a vertex to remove it (minimum
  three). Double-click a straight path segment to insert a projected polyline point.
  Both Bézier endpoints are labelled and focusable; each control is tethered to
  its own endpoint. Select either endpoint/control with the mouse or Tab and
  nudge it with arrow keys (Shift for larger steps).
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
  Creation, object movement, oriented resize, vertices, path points and ellipse
  parameters share snapping. Targets include polygon vertices/midpoints, path
  endpoints, ellipse centres/axes, and object edge/centre alignments. Guides and
  target marks are transient editor UI, including before the first object exists.
  Resize fixes the opposite anchor under rotated/nested/reflected transforms.
  Shift preserves proportions; square/equilateral/regular/circle locks require
  proportional scaling even without Shift. Alt bypasses snap only, never locks.
  Hiding the grid does not change snap preferences. Wheel zooms;
  Space-left-drag or the middle mouse button pans, including over geometry handles.
  Right-click on the canvas/tree opens shared contextual actions; Shift-right-click
  preserves the browser menu. Slash and a visible header button open local commands;
  **Scorciatoie** opens focus-owned help. A floating native canvas-command dialog
  keeps **Compatta/Guidata** as an exclusive segmented choice; switching retains
  both local drafts and performs no action. Both surfaces share the editor action
  registry, availability and validated vector creation (document units, bounded
  default size and placement in the visible canvas).
  Compact accepts a shape on the first Enter and creates it on the second. For
  triangles, `rect/right/left/isosceles/equilateral` (and Italian equivalents)
  refine the accepted shape before creation; right-angle defaults to the right.
  Suggestions, interpretation and defaults remain visible. Unknown input creates
  nothing; Escape cancels. Default bounding size is at most 120×100 document units
  and 70% of the visible world rectangle, centred in the current view. Presets fit
  within that box and stay native/constrained/editable. Switching variants keeps
  the accepted command/refinement; final creation is one undo step.
  Guided parameter/preview workflows are a separate follow-up capability.
  Text fields, menus and dialogs retain their
  keyboard behaviour, and Ctrl/Cmd+K remains global search. Ctrl+T is not intercepted.
- Numeric fields edit the local bounding corner’s scene position, dimensions
  along object axes, angle in degrees and the stored local pivot. Pivot drag/keys
  do not alter geometry; rotation uses it. Width-only edits preserve required
  preset ratios; incompatible paired dimensions and invalid matrices are refused.
  Edge/centre alignment and equal-gap distribution translate normalized selections.
  Compact numeric commands include `move/position/size/angle/pivot/radius/parent/align`
  (Italian aliases accepted); Guided exposes the same actions/validated parameters.
- Undo/redo is in-memory and bounded to 60 completed operations. A drag or
  property change is one step; view changes and selection are excluded.
- A stale save returns 409 and retains local work. **Salva come copia** creates
  a separate document; **Ricarica** asks before discarding local edits. Edits
  made during a normal save remain dirty after its earlier snapshot succeeds.
  Unloading a dirty editor prompts before leaving. Editor shortcuts belong only
  to the focused workspace; text fields retain typing/undo, dialogs own focus,
  and Ctrl/Cmd+S still saves from workspace text fields.
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
- Format version 3 stores an artboard and ordered polygon/ellipse/path/group
  nodes with stable node IDs, names, affine transforms, styles and visibility.
  Polygon vertices and path handles have node-scoped stable `pointIds`; authored
  anchors have IDs, names, positions and angles. Insert/remove/cut keep surviving
  identities; duplication changes node IDs while retaining scoped element IDs.
  Polygon vertices remain ordered coordinate pairs; edge visibility follows each
  outgoing edge. Paths use absolute M/L/C/Z commands. UI selection, viewport,
  handles and guides are not saved as artwork.
- Versions 1/2 are explicitly upgraded in memory on read. Version 1 receives
  deterministic IDs without inferred preset locks; version 2 retains existing
  locks/identities. Version 3 adds a nullable local transform pivot. Geometry,
  transforms and styles are unchanged. The
  database row is rewritten only by explicit Save; no schema reset is required.
  Unknown versions and version-2 metadata disguised as version 1 are rejected.
- Optional typed primitive constraints validate geometry in local and composed
  world coordinates. Incompatible point or parent transforms are refused; locks
  survive copy/history/save. **Sblocca geometria** removes only the constraint,
  retaining appearance and IDs, as one undo step. Preset creation UI is separate.
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
- Circles stay locked until explicitly converted to free ellipses; no circle-to-path
  conversion is supplied. Cuts are straight, boundaries are not welded, and
  polyline/cubic editing does not offer a full path-boolean toolset.
- Groups must be consecutive siblings to preserve overlap order. The layer list
  is a connected, collapsible scene tree. Group styling is not exposed.
- No angle snapping or zoom readout/fit control. Linked-asset overrides are
  deferred; stable native identities and numeric geometry are present.
- JavaScript is required for complete interactive rendering, including groups;
  the server-rendered first paint is not a complete no-JavaScript renderer.
