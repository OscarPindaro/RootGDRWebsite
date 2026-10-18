# Upload, guidance and reversible reconstruction

Oscar's preferred future interaction, recorded 2026-10-18:

1. Upload a drawing or reference.
2. Preserve the original and show the first extraction.
3. Let the person explain what a region means: a triangular feather, a
   trapezoidal blade, a cape with an intentional notch, an object behind a body.
4. Propose a deterministic fit or an explicit manual correction for that region.
5. Apply it as a typed, replayable operation; keep touching pieces attached.
6. Render the alternatives and let the person retain the better representation.

The user should not have to name region IDs or supply numerical coordinates.
The agent inspects the scene and translates the description into operations.
Those decisions remain visible in the recipe. Recognition, geometric fitting
and manual interpretation are different sources of information.

## Regularization

Semantic priors are supplied by the person or agent. Geometry can then be fitted:

- Remove almost-collinear or low-contribution vertices.
- Fit three contour runs as the sides of a triangle.
- Fit opposite sides of a four-sided blade as parallel trapezoid bases.
- Preserve shared attachment corners and explicitly marked details.
- Refuse a fit if its boundary drift or area change exceeds the chosen limits.

Different regions may need different treatment. A cape may reasonably keep seven
corners to preserve its hem; forcing five corners may erase an intentional detail.
Small vertex count is not the only objective.

## Preserve useful detail

Tacito's first extraction was preferred to the uniform-stroke post-processing,
especially for the head. Keep the original vector contours when fitting loses
expression. It is valid to regularize a sword while leaving facial details alone.

Objects should have complete geometry and explicit draw order where practical:
construct the sword, then place the character in front of it. A contour extractor
cannot observe the blade behind a head; reconstructing that hidden section is an
authored interpretation. Save that provenance instead of calling it detection.

## Current implementation boundary

`shape_edits.py` provides local inspection, shared anchors and JSON edit plans.
`polygon_regularizer.py` provides deterministic fitting with caller-selected
primitive families and tolerances. The interface is not yet a native canvas
workflow or a public MCP tool. It is the working prototype for that interaction.

During visual iteration, use short geometry/render checks. Oscar explicitly
requested no phone tests or long suites for this cycle.

## Generated body foundation

After reviewing the dressed drafts, Oscar clarified that the base body must be
one continuous polygon, not independently outlined limbs. Start naked, with no
objects. Each joint supplies two flesh points on its bisector at a declared
offset; connecting those sections defines the body boundary. The subsequent
correction uses OpenPose COCO_18, without custom head/jaw/pubic bones. The head
is a separately attached shape following Neck/Nose, not part of the body contour.
No physical neck column is added. Hands end in points; the inner hips join
directly without an extra central protrusion. Edit rig positions and offsets
and regenerate the skin before adding clothing or props.

Torso morphology also needs independent controls. Oscar's references distinguish
Tacito/Altus/Lizaárd's broader, tapered chest from J. Como's straight chest and
abdomen. A chest-height width station, and optionally a waist station, define
that silhouette without adding bones to OpenPose. Preserve the same rig while
comparing profiles so appearance changes are not confused with pose changes.

The numbered sketch clarifies the topology: start the torso at the shoulder
line, then derive the final contour from intersections with the limb surfaces.
Preserve an exposed torso corner when no limb covers it. An arm in front of the
chest keeps its visible side edges through upper arm and forearm, not just below
the elbow. Do not draw the construction caps across shoulder or elbow sections.
These visibility/layer choices are separate from the OpenPose joint coordinates.
