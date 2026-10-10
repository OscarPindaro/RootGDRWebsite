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

## Tracking

Initial intake key: `REQ-0015/T01`. Registered in Vikunja project **Root GDR**
(project ID **2**), task ID **2**; title, project and description confirmed by
read-back on 2026-10-10. No implementation-ticket decomposition, assignment,
priority or release is selected. Current ticket state belongs in Vikunja.
