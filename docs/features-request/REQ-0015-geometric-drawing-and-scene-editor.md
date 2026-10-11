---
id: REQ-0015
requested_on: unknown
title: Geometric drawing editor with reusable scenes and skeleton posing
recorded_on: 2026-10-10
---

# Geometric drawing and scene editor

## Request and motivation

Create original, stylized 2D characters, props, clothing and scenery directly in
Root GDR. The user's handmade characters define the visual language: strong
silhouettes, thick black outlines, flat colours, angular anatomy and a small
number of expressive details. The digital result should have crisp lines, not
simulated marker or pencil texture. Reuse a sword across characters or a tree in
future maps without redrawing it.

Both drawing/composition and basic skeleton posing belong in the requested
capability. This is feature intake, not implementation approval, prioritization,
release selection or an implementation-ticket plan.

## Current / desired behavior

Existing character and place specifications support images, and the document
editor has image-related capabilities. No matching scene-based drawing-editor
request was found in repository specifications or the real Root GDR backlog.
The generated geometric cover-art proposal is separate: this request is for
user-authored editable artwork.

Desired workflow:

1. Open an editor with a central drawing surface, shape tools and a hierarchy of
   scene objects/groups. The supplied sketch suggests a faint grid and side
   panels; it is a reference, not a final layout.
2. Create geometric shapes, move vertices, insert points along an edge, control
   fills and individual outlines, and compose curves or strokes for details.
3. Group objects into reusable scenes, save them in a global or world-specific
   library, and insert linked instances into another drawing.
4. Optionally import a skeleton preset, place rigid body parts on it and attach
   the head and props to anchors. Pose the figure by dragging hands or other
   endpoints while preserving bone lengths and respecting joint limits.
5. Save and reopen the complete editable drawing. Use it as a character portrait,
   insert it into site documents, export it, or compose a printable name/title
   card. A native scene document remains distinct from its rendered exports.

## Scope and constraints

### Shape editing and visual style

- Spawn triangles, rectangles, squares, circles and other basic polygons. Drag
  vertices and insert additional vertices on polygon edges.
- Altus's beak is the concrete editing example: start with a triangle, insert a
  point on its upper edge and another on its lower edge, then drag the original
  tip downward. The outline now has five vertices and a bent tip.
- Split a selected region into a separately editable, independently coloured
  shape, such as making the bent beak orange. Selecting the region's vertices is
  the user's suggested gesture; cut-path and polygon-splitting semantics remain
  a design question.
- Enable or disable individual boundary strokes while retaining the filled
  shape, so adjoining body parts need not have a black seam.
- Snap to meaningful geometry and attachment points. A subtle optional grid is
  suggested by the sketch; exact snap targets and controls remain open.
- Support decorative lines and curves for tattoos, facial details, scars and
  magic marks. Bézier editing is the user's suggested way to create tattoos.
  Faint details, such as ghosts inside Edeladra's dark cloak, must remain
  possible even though the overall rendering is crisp.
- Provide curated basic colour palettes to help a user who does not want to
  assemble every colour combination. Exact swatches are not yet selected.

### Scene composition and asset reuse

- Prefer a nested scene/group hierarchy. Characters, props, clothing and scenery
  use the same composition model; drawing order still controls front/back overlap.
- A sword can have a grip anchor attached to a hand point or authored anchor. It
  follows both the hand position and its intended orientation when posed.
- Reuse uses **linked instances with local overrides**, plus an explicit
  **make independent** action. Placement, size and colour can vary per instance
  without modifying the library original. Source geometry changes propagate to
  linked instances while preserving applicable overrides; detached copies do
  not receive subsequent source changes.
- The same relationship applies to skeleton presets. Scene-specific bone-length
  overrides remain local and are preserved when the preset changes. Structural
  conflicts caused by source edits need a later, explicit policy.
- Maintain both global and world-specific libraries. An admin can promote a
  world-local asset into the global library. Ownership/reference handling during
  promotion is not yet defined.

### Skeleton authoring and posing

- Include a dedicated skeleton-editing capability for authoring reusable presets
  with different proportions. Approximately three basic body types/sizes are a
  motivating example, not an agreed fixed preset count.
- The YOLO-style reference describes an easily inspected and edited keypoint/
  bone diagram. No machine-learning inference or pose detection is requested.
- Body parts behave like rigid paper cutouts, not a deforming skin or mesh.
  Start with simple unclothed bodies. Snap-on clothing is a desired extension;
  its initial coverage remains to be decided.
- Attach the head to the skeleton as well as held objects. Explicitly editing
  bone lengths inside a scene is allowed, separately from ordinary posing.
- Dragging a hand moves the connected arm with fixed segment lengths and joint
  constraints. Inverse kinematics is the technical interpretation, not a chosen
  library. Precise joint limits and unreachable-target behaviour remain open.
- Drawing a standalone sword, tree or other scene does not require a skeleton.

### Access, outputs and persistence

- Authoring is admin-only for now. Editing targets mouse and keyboard; full
  phone/tablet drawing support is not in the initial scope. Existing site/world
  viewing permissions must not be bypassed by publishing artwork.
- Save a native, editable scene representation including shapes, hierarchy,
  styles, linked sources, local overrides, anchors and skeleton state. Filesystem
  versus database storage and serialization are deliberately undecided.
- Support character portraits, illustrations in site documents, and printable
  cards containing a drawing, name and title.
- Download both PNG and SVG, each with a transparent or chosen background.
  An export must not replace or flatten the saved editable original.
- Provide undo and redo. Proposed conventional shortcuts are Ctrl+Z and
  Ctrl+Shift+Z, leaving Ctrl+X for cut; the initial message's shortcut spelling
  was ambiguous. History across reopening is not yet specified.
- Autosave is a proposal, not a confirmed requirement. Save cadence, recovery and
  concurrent editing need later decisions.
- Map reuse is a future goal; implementing a map editor is excluded. No animation
  timeline, realistic rendering, automatic tracing or AI generation is requested.
- UI copy is Italian; source, routes and stored specifications remain English.
  No renderer, frontend framework, library or storage schema is selected here.

## Acceptance criteria

1. An admin can create and edit the basic shapes and reproduce the five-vertex
   bent-beak workflow, then split and recolour the tip without losing the other
   region. Individual hidden outlines do not remove the fill.
2. The tools can represent the supplied style: Altus's angular head, crest and
   sword; Luciano's polygonal body; and curves, scars and faint decorative marks
   like those described for Edeladra and Tacito. Exact artwork reproduction is
   a later visual test, not artwork already implemented by this intake.
3. Objects can be grouped/nested, reordered and saved as reusable scenes. A sword
   attached at its grip follows hand position and orientation when the arm moves.
4. Editing a library asset updates its linked instances while retaining local
   placement/size/colour overrides. Making an instance independent preserves its
   appearance and prevents subsequent source edits from changing it.
5. An admin can author a reusable skeleton, import it into a scene, anchor a head
   and rigid body parts, and pose an arm while lengths and configured joint
   limits are respected. Explicit local bone-length edits do not alter the
   library preset or unrelated instances and survive applicable preset updates.
6. Both global and world-specific assets can be reused, and a local asset can be
   promoted globally. Non-admin users cannot mutate drawings, skeletons or
   libraries through either the UI or direct write requests.
7. A saved drawing reopens with editable geometry, hierarchy, styles, links,
   overrides, anchors and pose intact. Undo/redo covers authoring operations
   rather than only object movement; the exact history boundary remains open.
8. A drawing can be used as a character portrait and a document illustration,
   exported as PNG/SVG with either background option, and composed into a printable
   card with name and title. The native source remains editable afterward.
9. Mouse-and-keyboard authoring produces crisp digital artwork and offers a
   curated palette rather than requiring every colour to be chosen from scratch.

Proposed safeguards for later acceptance design: treat a complete drag as one
undo action; preserve original drawings when a linked-source update conflicts;
report inaccessible/missing sources instead of silently dropping scene objects;
keep internal editor controls, skeleton guides and snap guides out of exports.

## References

- [Character, place and document foundations](starting_description.md)
- [Existing document-image capabilities](../features-implemented/README.md)
- [Generated cover art: a separate proposal](desired_features.md#generated-cover-art-mondrian)
- [Frontend conventions](../frontend_guide.md)
- [Planning board and request tooling](REQ-0012-planning-and-release-tooling.md)

### User-supplied visual evidence

Nine JPEGs were supplied and visually reviewed in the intake conversation. The
user explicitly chose **Vikunja attachments**, not repository-stored image
assets, as their durable location. The repository retains this specification,
captions and confirmed task/attachment references only.

All nine images were uploaded to Vikunja task **2** on 2026-10-10. Metadata and
stored bytes were verified through the API using SHA-256. Repeating the upload
reused the same attachment IDs without creating duplicates. Local JPEGs remain
upload sources only and are not committed as repository evidence.

| Image | Attachment ID | Uploaded filename | Caption |
| --- | --- | --- | --- |
| 1 | 1 | `photo_2_2026-10-10_22-33-54.jpg` | Vertex dragging and inserting edge points to bend a beak; a sword's grip attaches to a hand and follows its direction. |
| 2 | 2 | `photo_1_2026-10-10_22-33-54.jpg` | Editor sketch with left shape tools, central grid, right object/group list; editable keypoint skeletons and reusable body-size presets. |
| 3 | 3 | `photo_7_2026-10-10_22-38-11.jpg` | Tacito, an angular wolf with exposed upper body, a large back-mounted sword, head/belly scars, facial tattoo, red trousers, belt and boots; blue accent strokes. |
| 4 | 4 | `photo_6_2026-10-10_22-38-11.jpg` | J. Como Salvasterzi: blue animal silhouette, red vest, yellow trousers, belt, tail and small separate accessories. |
| 5 | 5 | `photo_5_2026-10-10_22-38-11.jpg` | Lizard al Gaib: green lizard with an open angular jaw, polygonal hat, tan shirt, brown lower clothing and a belt-mounted kris/dagger. |
| 6 | 6 | `photo_4_2026-10-10_22-38-11.jpg` | Edeladra: fox head in a green cloak, fist-shaped brooch, dark interior, facial tattoo and turquoise magic strokes. The user describes faint ghost drawings inside the cloak that are difficult to discern in the photograph. |
| 7 | 7 | `photo_3_2026-10-10_22-38-11.jpg` | Luciano Piumalesta: guinea fowl with an approximately octagonal body, separate neck/head, angular wings and striped clothing. |
| 8 | 8 | `photo_2_2026-10-10_22-38-11.jpg` | Altus Fanfaron: triangular head with a downward-bent beak, three red triangular crest points, angular blue body/clothing and a large central sword. |
| 9 | 9 | `photo_1_2026-10-10_22-38-11.jpg` | Mario Fintonio: orange animal face with a broad grin, tall hat, purple jacket, bow tie, trousers and cane; combines polygons with rounded details. |

The paper texture and hand-drawn lettering in these references are not a request
for textured digital rendering or handwriting recognition. Printable cards do
need editable name/title text; font and layout choices remain open.

## Open questions

- Polygon splitting gestures, circle-to-path behaviour, selection tools and exact
  snapping targets/tolerances; how shared boundaries behave after later edits.
- Source revision/update timing and conflict handling when an overridden vertex,
  anchor or bone is renamed/removed; cycles, missing sources and asset deletion.
- Promotion semantics: move versus publish/copy, dependencies on other world-local
  assets, and what happens to existing instances and world visibility.
- Skeleton topology editing (including adding joints), supported body presets,
  joint ranges, root/pinned-point controls and unreachable targets. Clothing
  coverage and attachment behaviour; no cloth deformation is implied.
- Palette swatches, stroke controls, faint-detail opacity and any clipping tools.
- Native document format/storage, save/autosave workflow, recovery, concurrency,
  versioning and whether undo history survives closing the drawing.
- Portrait/document updates after editing the drawing: live references or
  explicitly published snapshots; export dimensions and card print dimensions,
  margins, typography and printing workflow.

## First workspace milestone

The approved first milestone is a standalone, admin-only **Disegni** area at
`/drawings`, independent of worlds. It uses native SVG and plain JavaScript in
the existing JinjaX shell, and a typed, versioned JSON document in PostgreSQL.

Saving is explicit: a Save button and Ctrl/Cmd+S, with stale-write rejection,
local work retained on failure, and an explicit Save as copy after a conflict.
Undo history is session-local. Desktop authoring includes polygon vertices,
individual outlines, straight chord cuts, local groups, lines/polylines and
cubic Bézier handles. Grid, vertex, midpoint and path-endpoint snapping are
placement aids, not persistent attachments. Cut pieces edit independently.
Circles remain ellipses; there is no circle-to-path conversion.

Phone support is viewing the artwork, not authoring it. The initial palette is
a curated starting point with custom colours and per-object opacity.

Linked libraries, world-local assets/promotion, anchors, skeletons/IK, publishing
into portraits/documents, downloads, printable cards, autosave and crash recovery
remain outside this milestone. They remain part of the parent request.
See the [drawing workspace manual](../features-implemented/drawing-workspace.md)
for the native format, interaction contract and limits.

## Workspace feedback tickets

The follow-up review requests five consecutive local implementation tickets:

- `REQ-0015/T09`: finish polygons reliably on double-click, without duplicate
  closing vertices; retain invalid drafts and explain the actual geometry error.
- `REQ-0015/T10`: include pure white and black in the predefined palette.
- `REQ-0015/T11`: a floating selection/action bar at the top of the artboard,
  with independent grid visibility, grid snap and geometry snap; move objects
  with snapping as well as individual vertices.
- `REQ-0015/T12`: replace separate layer cards/checkboxes with a connected,
  collapsible scene hierarchy, Godot-style, and eye controls on the right.
  Local parent/child relationships follow transforms and remain editable.
- `REQ-0015/T13`: expose both Bézier endpoints and their associated controls
  clearly in vertex mode, with reliable selection and editing.

User-supplied screenshots show the open polygon draft/error, the detached-looking
layer rows and the drawn character. These are feedback evidence, not new image
assets to commit. These local keys do not imply new board task registrations.

## Full-fledged editor planning decisions

The user approved registering a new authoring macro and granular tickets before
choosing an implementation order. This registers work; it does not start editor
implementation, select a preferred palette variant, assign a release or authorize
a push/deployment. The original reuse/skeleton/publishing/output requirements
remain in scope and must have their own tickets, not be silently dropped.

### Interaction and geometry

- Select belongs in the floating bar alongside shape editing and Transform.
  Creation still drags a bounding rectangle; single-shape selection then exposes
  direct geometry controls. Groups/multiple selections use appropriate whole-
  selection controls. The icons remain; a concise active-mode label was explained
  as a discoverability proposal, not a request to replace them.
- `T` enters Transform. `Ctrl+T` is only an optional alias after browser testing;
  the browser's New Tab shortcut cannot be promised universally.
- A triangle split button has a primary action preserving current isosceles
  creation and a submenu for equilateral and right triangles (right angle on the
  right or left; right is the default for that variant). Use valid main/menu
  buttons rather than nested clickable buttons.
- Presets stay geometrically locked until explicitly unlocked. Direct edits,
  group transforms, copy, undo and native persistence must respect locks. Do not
  infer new constraints on existing drawings just from an object name. Explicit
  conversion to freely editable geometry retains its appearance.
- Locked circles stay circular and expose centre/radius; ellipses expose two
  axes. Define how incompatible non-uniform parent transforms are refused or
  explicitly unlocked. Holding Shift preserves aspect ratio in Transform;
  persistent shape locks take precedence. Alt bypasses snapping, not locks.
- Apply enabled snapping to creation, movement, resizing, point and radius/axis
  edits with visible target feedback. Include meaningful edge/centre alignment;
  resizing keeps its opposite anchor fixed. Grid visibility remains independent.
- Middle-drag and Space-left-drag pan. Double-click an edge inserts a vertex in
  shape-edit mode; double-click polygon completion is a distinct creation action.
- The user means a right-click editor context menu, not overriding left-click or
  the whole website's browser menu. A visible button opens shortcut help.
- Delete means the selected subscene/object, including descendants, not the
  entire saved drawing. It is an undoable operation with a button and Delete key.
  Stacking controls use up/down arrows and clear forward/back labels.
- A rectangle that remains invisible after enabling visibility needs investigation:
  show the difference between hidden content, empty groups, disabled fill/stroke
  and no selection. Do not assume it is empty or repair data without evidence.

### Two floating canvas command palettes

Implement both variants behind a segmented two-button toggle, exactly one active,
so the user can compare them. The palette floats in the canvas/editor context;
commands create editable vectors with default dimensions rather than raster assets.

**Compact:** typing `triangle` shows that command, Enter accepts it, and a second
Enter creates the default triangle. Between those confirmations, subcommands such
as `rect` (right triangle), `right`/`left`, `isosceles` and `equilateral` refine the
variant. The right-triangle default is right. These are semantic examples; final
visible UI terms are Italian and internal action IDs are English. Suggestions must
show the interpreted command and defaults. Default dimensions and placement are
proposals to make explicit and bounded, not a fixed user-approved size.

**Guided:** choose an action and its contextual parameters, see a preview and apply.
Examples include shape/preset/dimensions, radius, movement, parenting and alignment.
Both variants use the same actions, validation, constraints and undo semantics.
Switching variants must not execute a command or silently discard a draft. Do not
remove either variant or select a winner before the user's comparison checkpoint.

Slash opens local canvas commands when editor focus owns the keyboard, with a
visible button as fallback. Ctrl/Cmd+K remains the reliable global site palette;
Alt+Space already exists but may be reserved by the desktop. Do not hijack text
editing, dialogs or unrelated page controls. The global palette must discover
accessible drawings and feature destinations; future feature delivery should
include both navigation and palette registration with permission-filtered results.

Numeric geometry, pivots, alignment/distribution, selection/viewport tools, edit
locks distinct from geometry locks, advanced curve tangents and recoverable local
drafts are proposed parts of the macro. Recovery must not silently introduce server
autosave: explicit Save remains the confirmed persistence model.

### Ticket decomposition and draft dependency order

Historical workspace keys T02–T14 are backfilled from their existing local commits;
those implementations do not include the newly approved locked-preset/command scope.
The new authoring macro is **REQ-0015/T15**; T16–T31 are its child tickets. The
remaining original scope T32–T45 belongs to the original parent **REQ-0015/T01**.
Current board state belongs only in Vikunja; these keys specify scope/dependencies.

| Key | Deliverable | Prerequisites |
| --- | --- | --- |
| T16 | Shared actions, focus ownership, Select/Edit/Transform states | T08, T11, T12, T13 |
| T17 | Native constraints, stable element IDs and safe format migration | T03 |
| T18 | Split-button locked triangle/rectangle/polygon presets | T16, T17 |
| T19 | Circle/ellipse parameters and ratio/group-transform invariants | T17, T18 |
| T20 | Resize snapping, alignment guides and Shift-proportional transforms | T16, T18, T19 |
| T21 | Subscene deletion, invisible-object diagnosis and vertical order controls | T12, T16 |
| T22 | Context menus, pointer/keyboard ownership and shortcut help | T16, T21 |
| T23 | Site-wide feature/drawing palette discovery | T16 |
| T24 | Shared floating canvas command framework and exclusive variant toggle | T16, T22, T23 |
| T25 | Compact incremental command/subcommand palette | T24, T18, T19 |
| T26 | Guided parameter/preview palette | T24, T27 |
| T27 | Numeric geometry, pivots, alignment and distribution | T16, T17, T20 |
| T28 | Marquee/deep selection, object locks, fit controls and zoom readout | T16, T21 |
| T29 | Local draft recovery and safe navigation with explicit server Save | T16, T17, T24 |
| T30 | Advanced curve anchor/tangent editing and shape-preserving insertion | T13, T16, T17, T27 |
| T31 | Authoring acceptance and user comparison of both command variants | T18–T30 |
| T32 | Global/world reusable scene libraries and permissions | T17, T31 |
| T33 | Linked instances, local overrides and make-independent | T32 |
| T34 | Source revisions, structural conflicts, cycles and missing/deleted sources | T17, T33 |
| T35 | World-to-global promotion policy and implementation | T32, T34 |
| T36 | Authored anchors and oriented grip/head/accessory attachments | T17, T33, T34 |
| T37 | Skeleton authoring and reusable body-proportion presets | T17, T32 |
| T38 | Rigid body assembly, heads/props and initial snap-on clothing | T36, T37 |
| T39 | Constrained IK, unreachable targets and local bone-length overrides | T34, T38 |
| T40 | Permission-safe publication/reference contract | T32, T34 |
| T41 | Drawing-based character portraits | T40, T43 |
| T42 | Authored illustrations in site documents | T40, T43 |
| T43 | PNG/SVG export, background options and guide-free resolved artwork | T34, T39 |
| T44 | Printable artwork/name/title cards | T43 |
| T45 | Full original-request acceptance and native compatibility audit | T35, T39, T41, T42, T44 |

Suggested sequential order, not priorities/dates or permission for parallel agents:
**T16 → T17 → T18 → T19 → T20 → T21 → T22 → T23 → T24 → T25 → T27 → T26 →
T28 → T29 → T30 → T31 → T32 → T33 → T34 → T35 → T36 → T37 → T38 → T39 →
T40 → T43 → T41 → T42 → T44 → T45.** Numeric IDs are identifiers, not execution
order. T16/T17, T21/T23 and later branches have some conceptual independence, but
shared files and runtime/database ownership mean sequential work is the default.

Promotion/reference policies, skeleton topology/limits/unreachable-target behaviour,
clothing coverage and card dimensions remain explicit decision gates in their
own tickets. No map editor, animation, tracing, handwriting recognition or AI
art generation is added. Each implementation needs real persistence/permission
checks, relevant tests/build, desktop and phone evidence and a scoped local commit.

## Tracking

Initial intake key: `REQ-0015/T01`. Registered in Vikunja project **Root GDR**
(project ID **2**), task ID **2**; title, project and description confirmed by
read-back on 2026-10-10. Original parent:
[REQ-0015/T01, task #2](http://192.168.1.201:3458/tasks/2).
New authoring macro:
[REQ-0015/T15, task #8](http://192.168.1.201:3458/tasks/8).

Confirmed registration/read-back maps historical T02–T14 to task IDs
**11–23**, authoring T16–T31 to **24–39**, and remaining original scope T32–T45
to **40–53** respectively. Every child description/comment links its verified
parent and prerequisite task URLs; the macro and original parent have reciprocal
indexes. The original reference attachments 1–9 remain on task #2.

Native parent/dependency creation was denied by the current tooling token.
These are verified hyperlinks, not claimed native Vikunja relations; owner approval
of `tasks_relations.create` is required. Related tooling:
[REQ-0012/T10, task #9](http://192.168.1.201:3458/tasks/9).
The opt-in implementation workflow is separately tracked as
[REQ-0012/T11, task #54](http://192.168.1.201:3458/tasks/54), with
`.devin/skills/implement-ticket/SKILL.md` as its source.

No assignment, priority, due date or release is selected here. Current ticket
state belongs in Vikunja; local commits/evidence are not thereby pushed or deployed.
