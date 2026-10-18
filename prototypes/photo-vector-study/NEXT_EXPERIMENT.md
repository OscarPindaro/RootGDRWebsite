# New characters and a synthetic pose dataset

Recorded from Oscar's direction on 2026-10-18. This is the next experiment,
after the current photo reconstruction and guided edits; no dataset or trained
model is claimed here.

## First visual trial

Oscar clarified the first step after reviewing the clothed drafts:
**start naked, with no objects and one continuous body polygon**. His next
correction specifies OpenPose COCO_18, a separate head shape aligned to the pose,
pointed hands, and no drawn neck column or invented pubic point. The skeleton
defines bone positions; flesh comes from paired bisector offsets on the limbs.

`body_skin.py` implements that contour walk; `generate_bodies.py` renders five
construction examples. `output/generated/index.html` can show the skeleton,
bisector cross-sections and their skin endpoints. It does not render separate
limb polygons or joint seams. The head has a separate asset/pivot transform for
future animation. The earlier clothed draft was set aside.

Review this foundation before adding clothing, props or generating 1,000 examples.
New character appearance and layering are subsequent steps, after continuous
skin construction is accepted.

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
Later tools may add semantic regions on the continuous skin, clothing attachment,
transforms and regeneration from rig parameters. Native canvas integration and a
full MCP service remain separate implementation work.
