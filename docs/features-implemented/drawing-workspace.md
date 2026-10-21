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
- Select through the canvas or connected scene tree; Shift, Ctrl and Cmd each
  add to the selection in the tree, so two rows can be picked and grouped. The
  rows are separated by a rule. A single click always selects; renaming is a
  double-click on the row's name (or F2), which swaps the name for a field in
  place — Enter commits, Escape restores. A locked row cannot be renamed.
  Canvas clicks select whole top-level groups; Ctrl/Cmd-click selects
  deeper children. Empty-canvas marquee fully encloses visible editable root
  subscenes; Shift adds them and Ctrl/Cmd+A selects the same eligible roots.
  Ancestors/descendants are never transformed twice. Groups expand/collapse, eye
  controls toggle visibility, and tree arrows/Home/End never nudge artwork.
  Tree edit locks cover nodes/subtrees and prevent moving a containing group,
  independently of visibility and primitive constraints. Locked artwork is
  skipped by canvas picking but accessible in the tree. These are authoring aids,
  not permission controls. Fit drawing/selection and zoom readout affect only view.
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
  **Taglia** draws an unbounded line: drag to place it, drag its middle to move
  it or either handle to turn it, then Enter splits **every selected** polygon
  along it into two pieces. The line is editor state, not document state: it is
  never in the saved scene, it disappears when it is applied, and Escape puts it
  away without touching the artwork. A line that misses a polygon, that would
  leave a piece without area, or that would leave a piece touching itself (a U
  cut across its own arms) is refused with an explanation, and locked presets
  cannot be cut. Pieces edit independently and the seam the cut made starts
  hidden on both.
- **Raggruppa** combines consecutive sibling objects; **Separa** composes the
  parent transform into the children. Nested child edits use the complete
  parent transform. Hidden groups are excluded from canvas selection.
- A curated fourteen-colour palette, including pure white and black, custom
  fill/stroke colours, width and opacity
  support angular silhouettes and faint details. For paths, palette choices
  change the stroke colour. The paint controls sit in the left rail beside the
  tools, so they are on screen without scrolling the inspector; the chips wrap
  to the rail's width.
- The inspector is a list of compact rows: **Posizione** (X and Y), **Dimensione**
  (length and height), **Rotazione** and **Pivot** (X and Y) each share one line,
  and the ellipse centre/radius rows follow the same shape. Values are document
  units; the axis letter is decorative and every field keeps its own accessible
  label. The right rail holds identity (name, parent) and geometry; paint lives
  on the left.
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
  Hiding the grid does not change snap preferences, and the grid itself is either
  lines or points, chosen from the editor menu. The preset submenus name their
  shape with an icon, so a variant is recognisable before it is read.
  Wheel zooms; Space-left-drag or the middle mouse button pans, including over
  geometry handles.
  Right-click on the canvas/tree opens shared contextual actions; Shift-right-click
  preserves the browser menu. Slash and a visible header button open local commands;
  **Scorciatoie** opens focus-owned help. The command palette is docked inside the
  canvas, at its top centre, not a modal over the application: it never covers the
  page chrome, the canvas stays usable around it, and Escape or its close control
  returns focus to whatever opened it. It keeps **Compatta/Guidata** as an
  exclusive segmented choice; switching retains both local drafts and performs no
  action. Both surfaces share the editor action registry, availability and
  validated vector creation (document units, bounded default size and placement in
  the visible canvas).
  Compact runs in two stages. The first Enter accepts a shape; the second creates
  it. Between them the text refines the accepted shape: a number is the bounding
  box width (the other dimension keeps the shape's default ratio), a number on a
  regular polygon is its vertex count (3–32), and a triangle also takes
  `rect/right/left/isoscele/equilatero` (and English equivalents) in either order,
  so `130 isoscele` and `isoscele 130` agree. Right-angle defaults to the right.
  Suggestions, the interpretation and the resulting size stay visible. Unknown or
  out-of-range input creates nothing; Escape cancels. Default bounding size is at
  most 120×100 document units and 70% of the visible world rectangle, centred in
  the current view. Presets fit within that box and stay native/constrained/editable.
  Switching variants keeps the accepted command/refinement; final creation is one
  undo step.
  Guided offers contextual shape/preset/dimension, radius, movement, parent and
  alignment fields. Its SVG preview uses the same validated native operations
  against a cloned scene; the original/history stay unchanged until **Applica**.
  Escape discards only the preview. Fields survive variant/action switching, both
  modes remain available, and a completed command is one undo step.
  Text fields, menus and dialogs retain their
  keyboard behaviour, and Ctrl/Cmd+K remains global search. Ctrl+T is not intercepted.
- Curve anchors expose corner (independent), smooth (opposite direction, separate
  lengths) and symmetric (opposite equal tangents) modes. Moving an endpoint carries
  its attached controls; controls remain snap-aware and keyboard reachable. The
  insert-point action splits the selected cubic segment at its midpoint using
  de Casteljau, preserving appearance and existing endpoint identities. New midpoint
  identity/mode, copy and undo/reopen retain editable multi-segment cubic semantics.
- **Promotion** copies a world asset into the global library. The right it checks
  is the right to *write* the global library, which is the administrator's, not
  the right to read the source — so a world master may author a world library and
  still cannot publish into the global one. The copy is a new asset with its own
  identity, the source section is recreated by name, and provenance records the
  asset it came from; the world asset, and every instance pointing at it, are left
  exactly as they were. Promoting something already global is a conflict, not a
  second copy. Nothing rewrites existing instances, so promotion can never change
  a drawing that already exists.
- A library asset may not contain itself, directly or through another asset. Both
  writes that could create such a cycle — saving an asset and refreshing an
  instance — refuse it with a conflict, and the refusal changes nothing. A link
  to an asset that does not exist yet is allowed, because the source may be
  authored later and the drawing already holds the artwork. Refreshing a linked
  instance against a source that has been deleted reports it and leaves the
  resolved artwork exactly as it is; a revision whose merge would break the
  drawing's constraints is refused the same way. Both are reported, never
  silently applied or silently dropped.
- An inserted asset is a copy by default. Choosing **Collega all'originale**
  instead makes it a *linked instance*: one node that keeps the source library
  and asset ids, the revision it was resolved at, and the subtree the library
  drew at that moment. The subtree is stored, not fetched, so a drawing renders
  and stays editable with the library gone, and a missing source is reported
  rather than dropped. Edits inside a linked copy — placement, fill, outline,
  opacity, visibility — are recorded as local *overrides* on the instance, and
  refreshing from the library takes the new revision while keeping exactly those
  aspects and everything else from the source. Nodes are matched by their source
  identity, so a fragment that gained or lost a node still merges. **Rendi
  indipendente** breaks the link: the children become plain nodes with fresh
  identities, the instance's own transform, opacity and visibility composed into
  them so nothing moves, and the whole thing is one undo step.
- A **library** holds reusable authored parts. A library is global or belongs to
  one world, and it is divided into sections the librarian creates. An asset
  stores a *scene fragment*: native nodes with their geometry, styles,
  constraints and identities, never a rendered preview, so inserting one brings
  editable artwork. The editor's library panel saves the current selection as an
  asset and inserts an asset as an **independent copy with fresh identities** —
  linking an instance to its source is a later ticket. Read and write follow one
  narrow rule: an administrator may use any library, a world library is also open
  to that world's master, and nobody else sees it at all. A library a caller may
  not read is reported as absent rather than forbidden, so its existence is not
  leaked, and listing returns bounded metadata (id, name, section, node count,
  version) with the geometry only on the single-asset read.
- The artboard is an editable rectangle: its width, height and background are
  document data, set from the inspector and undoable like any other change. It is
  a **soft guide**, not a clip — the editor shows a quarter of the artboard's size
  around every edge, so artwork drawn past it stays visible on the page while the
  artboard itself keeps its own background and rule. The SVG view box and the
  element's aspect ratio follow the document, not a fixed token. A drawing
  therefore has two rectangles an export can use: the artboard, or the bounds of
  everything visible (`contentBounds`), which is the current no-canvas-size
  behaviour.
- Numeric fields edit the local bounding corner’s scene position, dimensions
  along object axes, angle in degrees and the stored local pivot. Pivot drag/keys
  do not alter geometry; rotation uses it. Width-only edits preserve required
  preset ratios; incompatible paired dimensions and invalid matrices are refused.
  Edge/centre alignment and equal-gap distribution translate normalized selections.
  Compact numeric commands include `move/position/size/angle/pivot/radius/parent/align`
  (Italian aliases accepted); Guided exposes the same actions/validated parameters.
- Recovery is best-effort browser-local storage, scoped to authenticated user UUID
  and drawing UUID. It retains completed edits/title and unfinished polygon,
  dragged line/curve and command drafts, without server autosave. Seven days is a
  soft age warning; no automatic artwork/cache deletion occurs. Restore/discard
  is explicit before further authoring; restored scenes pass the admin-only native
  validation endpoint. A stale draft retains its old expectedVersion and offers
  Save as copy, so newer server content cannot be overwritten. Storage/access
  failures preserve work and explain that it is not confirmed server persistence.
  App links and global search offer Save/Discard/Cancel; pending writes cannot be
  discarded. Browser reload/back keep the native leave warning and flush recovery.
- Automatic saving is opt-in from the editor menu and stored browser-locally per
  user, like the other editor preference. When on, it saves once two idle seconds
  after the last change: a drag or a run of edits is one save, and it never fires
  mid-gesture, while a request is in flight or while a recovery choice is pending.
  Explicit Save, the conflict actions and stale-write rejection are unchanged.
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
- Format version 5 stores an artboard and ordered polygon/ellipse/path/group
  nodes with stable node IDs, names, affine transforms, styles and visibility.
  Polygon vertices and path handles have node-scoped stable `pointIds`; authored
  anchors have IDs, names, positions and angles. Insert/remove/cut keep surviving
  identities; duplication changes node IDs while retaining scoped element IDs.
  Polygon vertices remain ordered coordinate pairs; edge visibility follows each
  outgoing edge. Paths use absolute M/L/C/Z commands. UI selection, viewport,
  handles and guides are not saved as artwork.
- Versions 1/2/3/4 are explicitly upgraded in memory on read. Version 1 receives
  deterministic IDs without inferred preset locks; version 2 retains existing
  locks/identities. Version 3 adds a nullable local transform pivot; version 4
  adds default-unlocked object/subscene edit locks; version 5 stores endpoint-bound
  corner/smooth/symmetric curve modes. Older curves retain independent tangents.
  Geometry,
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

- No anchors,
  skeletons, portrait/document publishing,
  PNG/SVG downloads, card printing, animation, imports or clipping.
- Explicit server saving only: local recovery is browser-storage-dependent and
  undo history is not persisted.
  A failed/ambiguous response does not claim successful persistence; inspect or
  reload server state before treating local work as durable.
- Circles stay locked until explicitly converted to free ellipses; no circle-to-path
  conversion is supplied. A cut is one straight line at a time, boundaries are not
  welded, and polyline/cubic editing does not offer a full path-boolean toolset.
- Groups must be consecutive siblings to preserve overlap order. The layer list
  is a connected, collapsible scene tree. Group styling is not exposed.
- No angle snapping, and no per-drawing artboard preset beyond editing the two
  numbers. Linked-asset overrides are
  deferred; stable native identities and numeric geometry are present.
- JavaScript is required for complete interactive rendering, including groups;
  the server-rendered first paint is not a complete no-JavaScript renderer.
