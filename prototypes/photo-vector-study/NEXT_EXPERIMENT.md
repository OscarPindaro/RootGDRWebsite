# New characters and a synthetic pose dataset

Recorded from Oscar's direction on 2026-10-18. This is the next experiment,
after the current photo reconstruction and guided edits; no dataset or trained
model is claimed here.

## First visual trial

Generate a small contact sheet of about twelve **new** characters in the same
geometric language as Altus, Luciano and Tacito. Use a declared skeleton, a head
family, body proportions, and independently attached clothes/props. Vary poses
as well as appearance. Inspect this batch before scaling toward 1,000 examples.
The first question is whether the generated characters are worth drawing.

Use the examples' visual vocabulary: triangular/bent beaks, angular wolf heads,
octagonal bird bodies, strong outlines, flat colours, capes, hats and swords.
Generate new combinations and proportions without inventing story canon.

## Keep the ground truth

Each generated image should retain:

- seed, character-family ID, rig topology and joint coordinates;
- joint presence, visibility and occlusion as separate attributes;
- bone lengths, joint limits, attachment points and current transforms;
- native shape geometry, part IDs, clothing/prop layers and draw order;
- rendered image, part masks, bounds and crop/image transforms.

A round bird must not acquire fictional human knees inside its torso merely to
fill a fixed 17-point annotation. The rig defines which joints exist. Clothing
can hide a joint that still exists; that is different from an absent joint.

## Scaling toward 1,000

Diversify heads, body proportions, rig families, poses, colour palettes, clothing,
held objects, overlap and partial visibility. Include both clean vectors and
photo-like render variations (paper, perspective, lighting, stroke variation),
while applying the same image transforms to every annotation.

Split train/validation/test by character family or generator template, not only
by image seed. Near-identical recolourings of one template must not occur on both
sides of the evaluation. Reserve real hand-drawn examples as a separate check.

Compare a pretrained pose model, a fine-tuned model and simpler geometry-based
methods before deciding what to train. A thousand images is a useful experiment,
not evidence that a general pose estimator will work. Measure visible and
occluded joints separately, and evaluate on drawings outside the generated style.

## Iterative authoring

The intended loop is: import → inspect detected geometry/pose → add a description
→ apply a typed edit plan → validate shared points → render and compare.
The current `shape_edits.py` CLI is the first prototype of that interface.
Later tools may add named body-part groups, skeleton binding, clothing attachment,
transforms and regeneration of selected parts. Native canvas integration and a
full MCP service remain separate implementation work.
