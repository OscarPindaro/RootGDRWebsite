# Photo → polygon study

First visual experiment for Oscar's Altus, Luciano and wolf drawings.
The Python data records manually interpreted vertices in the original 768 × 1024
photo coordinates. It is an annotated reconstruction, not a general automatic
photo converter. Nothing is imported into the application.

The scripts, gallery HTML, SVG/JSON scenes, PNG review images, and the three
original photographs in `output/references/` are tracked in Git. A checkout can
open `output/shapes/index.html` directly without installing the model libraries.
Model caches and ZIP downloads are excluded. Run
`uv run --no-project package_study.py` to prepare the optional `output/study.zip`.
Large photographic review PNGs use an indexed palette to stay below the
repository's file-size gate; the source JPEGs and vector geometry are preserved.
Regenerate the OpenCV crops from those JPEGs before repeating model inference.

| Character | Semantic groups | Filled polygons |
| --- | ---: | ---: |
| Altus | 12 | 22 |
| Luciano | 11 | 20 |
| Wolf | 15 | 23 |

`drawings.py` holds typed Pydantic data. `render.py` writes transparent SVG/PNG,
JSON coordinates, a group/vertex map, a PNG contact sheet and a local comparison
gallery. Filled shapes use only polygons; ink details use open polylines.
SVG groups and individual shapes have stable English IDs. Z-order follows the
data order. Group colours and vertex dots appear only in the diagnostic maps.
PNG previews are 1,400 pixels high.

Altus's outer turquoise/purple cape is omitted. The small gloves and arm
boundaries are interpretations of the partly obscured grip. No hidden legs are
invented. Luciano retains an eight-vertex body, with separate stripe polygons.
The wolf retains its pose, teeth, scars, belt and rear sword; the blue motion
marks and handwritten captions are omitted. Photographic perspective is retained.
These are visible-part groups, not rigged or independently complete limbs.

## Reproduce

From this directory:

```sh
uv run --no-project render.py --photos /path/to/altus.jpg /path/to/luciano.jpg /path/to/wolf.jpg
```

Without `--photos`, SVG/PNG/JSON and the gallery still regenerate; existing cropped
references are reused if present. Dependencies are pinned in the scripts, outside
the project's environment and lockfile. Contact-sheet text uses the system
DejaVu Sans font. The model cache and ZIP bundles are ignored by Git.

Open `output/index.html` directly, or serve **only `output/`** on loopback:

```sh
python -m http.server 8766 --bind 127.0.0.1 --directory output
```

## Pose probe

`pose_probe.py` uses MediaPipe Pose Landmarker Full, float16, version 1.
It tries each original photo and a character crop at detection/presence
thresholds 0.5 and 0.25: twelve trials in total.

```sh
mkdir -p .cache
curl --fail --location \
  https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task \
  -o .cache/pose_landmarker_full.task
uv run --no-project --python 3.12 pose_probe.py \
  --model .cache/pose_landmarker_full.task \
  --photos /path/to/altus.jpg /path/to/luciano.jpg /path/to/wolf.jpg
```

Observed on the supplied photographs:

- At 0.5, all six inputs yield zero poses.
- At 0.25, only Luciano's crop yields a pose. Visual inspection shows the model
  putting limb landmarks inside the torso rather than following wings and feet.
- Altus and the wolf yield zero poses at both thresholds.

The output JSON preserves all returned coordinates, presence and visibility;
the overlay deliberately shows even unreliable landmarks so the failure is
visible. This baseline does not establish that every pose model will fail.
No estimated landmarks were used to build the SVGs.

The next useful steps are a visual correction pass, conversion into native
canvas shapes, then explicit joints and attachment points. Hidden geometry and
the intended joint structure need authoring before the figures can be animated.

## Automatic OpenCV experiment

`opencv_trace.py` is a separate pixel-driven pipeline. It does not import
`drawings.py` or use its annotated coordinates, crop boxes or palette. Only the
input filenames and display names are supplied; parameters are shared across
all three photos.

```sh
uv run --no-project --python 3.12 opencv_trace.py \
  --photos /path/to/altus.jpg /path/to/luciano.jpg /path/to/tacito.jpg
```

Outputs live in `output/opencv/`, with their own comparison gallery:

1. Find the largest light, low-saturation paper quadrilateral.
2. Apply a perspective transform.
3. Isolate the largest connected foreground drawing.
4. Separate dark ink from coloured fills using HSV thresholds and morphology.
5. Find connected fill regions; split strong colour differences where an ink
   gap has joined them. Estimate fill colours from the image medians.
6. Extract contour loops and simplify with Douglas–Peucker. Detailed traces
   use at most 0.8 pixels of tolerance; polygon traces use at most 3 pixels.
   Small details use a proportionally smaller tolerance.

SVG paths contain straight closed contour loops with even-odd filling for holes.
The detailed version represents curves with more vertices; it does not fit
Bézier curves. Region IDs are generic and carry no anatomical meaning.
The underlying ink silhouette and detected fills are individually grouped.
Altus's cape is included in this experiment.

The gallery also exposes the paper detection and region masks. Remaining limits:
small white details can be lost or merge through broken ink boundaries; some
motion marks that touch the character survive; strokes retain variable marker
thickness; pale enclosed background cannot be distinguished from white clothing.
The same parameters worked on these three images, not a validated general dataset.

### Tacito pose follow-up

The original photo and original crop had no detections. A follow-up tests the
automatically rectified crop, isolated crop, and isolated crop with 15% extra
padding, each at thresholds 0.5 and 0.25. At 0.5 all three yield zero poses.
At 0.25 only the padded image yields a pose, with head/upper-body landmarks
around the trousers: visual inspection rejects it.

A human positive control yields a correctly placed pose at 0.5. Its source is
Google's sample: <https://storage.googleapis.com/mediapipe-assets/pose.jpg>.
This supports that the model runs correctly, while these cartoon inputs remain
unsuitable for this particular model/configuration.

```sh
curl --fail --location https://storage.googleapis.com/mediapipe-assets/pose.jpg \
  -o .cache/pose-positive-control.jpg
uv run --no-project --python 3.12 pose_probe.py \
  --model .cache/pose_landmarker_full.task \
  --photos /path/to/altus.jpg /path/to/luciano.jpg /path/to/tacito.jpg \
  --processed-dir output/opencv --character wolf \
  --control .cache/pose-positive-control.jpg --output output/opencv
```

Rerun `opencv_trace.py` after the pose probe to include its diagnostic links in
the gallery. The probe never supplies coordinates to either vector renderer.

## Illustration-trained pose experiment

`humanart_probe.py` uses RTMlib 0.0.16 with the official HumanArt versions of
**YOLOX-m** (character detection) and **RTMPose-l** (17 COCO body keypoints).
Both checkpoints come from the
[MMPose HumanArt model catalogue](https://github.com/open-mmlab/mmpose/tree/main/projects/rtmpose#body-2d).
Inference runs locally through ONNX Runtime on CPU.

```sh
uv run --no-project --python 3.12 humanart_probe.py
```

Models are downloaded to `.cache/humanart/`; source URLs and model SHA-256 hashes
are recorded in `output/humanart/results.json`. The test consumes the rectified
and isolated OpenCV crops, without using manually traced shapes or correcting
predicted joints. Output coordinates are in each crop's pixel space, the same
space used by the corresponding automatic SVG.

There are separate trials for automatic detection and crop-assisted inference.
The latter explicitly supplies the whole OpenCV crop as a bounding box; it is
not evidence of a successful character detection. RTMlib silently falls back to
the full image for an empty box list, so the probe skips inference when the
detector fails rather than treating that fallback as a detection.

Observed results at detector threshold 0.3:

- **Tacito:** detected in both crop variants. All 17 joints exceed display score
  0.3. Visual inspection shows a plausible body pose following the raised arms,
  bent knees, hips and ankles. Facial points remain approximate human landmarks.
- **Luciano:** detected, with 15 joints exceeding 0.3. The model imposes human
  leg anatomy inside the octagonal body; this needs author correction.
- **Altus:** no automatic detection. Crop-assisted inference returns 11 points
  above 0.3, but confuses the cape with arms and does not recover the sword grip.
- **Human control:** detected with 17 points above 0.3.

`output/humanart/index.html` compares automatic detection with crop-assisted
results. JSON retains every predicted score and coordinate, including points
hidden below the display threshold. These are initial estimates, not an
accuracy benchmark or an implemented animation rig.

### Additional models tested

- [`dghs-imgutils`](https://dghs-imgutils.deepghs.org/HEAD/api_doc/pose/index.html)
  0.19.0 was tested through its actual `dwpose_estimate` API, using DWPose.
  Automatic character detection returns no detections for all three drawings.
  Crop-assisted inference gives a weak partial leg estimate for Tacito and
  little useful body information for the birds. The human control is detected.
- [Bizarre Pose Estimator](https://github.com/ShuhongChen/bizarre-pose-estimator)
  was tested with its `feat_match+data` checkpoint, using the same OpenCV crops.
  It confuses Tacito's head, hips, limbs and sword. Its bundled anime example
  gives a plausible pose, confirming a useful sanity control.

HumanArt remains the strongest body-pose estimate for Tacito in these tests.
The comparison is qualitative, without manually annotated ground truth.
`output/pose-comparison/index.html` shows the three crop-assisted runs together;
each model's raw results remain in its own output directory.

```sh
HF_HOME="$PWD/.cache/huggingface" uv run --no-project --python 3.12 dwpose_probe.py
uv run --no-project --python 3.12 bizarre_probe.py
uv run --no-project compare_poses.py
```

Bizarre requires a one-time setup:

```sh
mkdir -p .cache/bizarre
git clone https://github.com/ShuhongChen/bizarre-pose-estimator.git .cache/bizarre/source
git -C .cache/bizarre/source checkout b72005c2521c42c34df5c91c3660abab4a86a00c
curl --fail --location \
  https://huggingface.co/h54917/bizarre-pose-estimator/resolve/main/bizarre_pose_models.zip \
  -o .cache/bizarre/models.zip
python - <<'PY'
from pathlib import Path
from zipfile import ZipFile
root = Path(".cache/bizarre")
with ZipFile(root / "models.zip") as archive:
    name = next(n for n in archive.namelist() if n.endswith("/feat_match+data.ckpt"))
    (root / "feat_match+data.ckpt").write_bytes(archive.read(name))
PY
```

`bizarre_probe.py` is an inference-only adaptation of the authors' feature-matching
architecture, under **AGPL-3.0**, kept in this standalone experiment. The training
Detectron2 teacher is not used by that model's inference branch. Every inference
weight is loaded strictly. The port's raw heatmap output matches the unmodified
upstream forward method exactly on a deterministic check (maximum error 0).
The tagger's 256-pixel input size was checked against its bundled checkpoint.
The old segmentation stage is replaced by the already available OpenCV crop.
The checkpoint comes from the linked public mirror; its SHA-256 and upstream
commit are recorded in the result. Model downloads total several GB and are
cached outside Git.

DWPose/HumanArt display joints above score 0.3; Bizarre follows the original
visualization and displays all 17 proposed joints. Its smoothed heatmap peaks
are not directly comparable to the other models' confidence scores.

## Reconstruction as independent shapes

`reconstruct_shapes.py` consumes the automatic contour JSON and ink masks.
It never reads the hand-authored points from `drawings.py`. It saves that detected
scene as `*-detected.json`, then applies the explicit user-guided recipes in
`edits/`. `--no-edits` renders the purely automatic reconstruction.

```sh
uv run --no-project --python 3.12 reconstruct_shapes.py
```

Rather than keeping a black silhouette behind coloured patches, it recovers
boundary centres by assigning ink pixels to the nearest fill or background.
It then fits straight edges, regularizes nearly horizontal/vertical edges,
and replaces the photographed outlines with consistent SVG strokes. Small
details use thinner strokes. Compact rounded marks can become ellipses when
their fitted overlap exceeds 90%.

Remaining internal ink is thinned into paths. Nearly straight paths become
lines; curved paths become cubic Bézier segments with explicit control points.
Tacito's muzzle curl is preserved this way. Shared colours, joins and partial
occlusions still limit reconstruction; small features can be simplified, and
motion marks touching the character may remain.

Each polygon, ellipse, line or Bézier is an independent SVG object with an ID
and source-region reference. The typed JSON records fill, stroke, geometry and
curve controls in the OpenCV crop's coordinate space. Its
`photo-shape-study` format is an experimental interchange format, **not** the
application's native drawing schema. It contains visible shapes, not recovered
anatomical parts, hidden limbs or a rig.

`output/shapes/index.html` compares the reference photograph, the first OpenCV
trace, and the corrected reconstruction. Click the photo to open the unmodified
source JPEG. The first trace keeps the marker's uneven ink boundary; the final
version uses fitted shapes and independently specified outlines.
Click a shape to select it; **Separa gli oggetti** temporarily spreads them apart.
These inspection controls do not change the saved SVG or JSON. The gallery links
to the PNG comparison, individual SVG/JSON files, and a coloured object map.

## User-guided geometric corrections

The 2026-10-18 recipes record Oscar's added information:

- Outlines are 35% thicker, including small details.
- Altus's yellow collar is a three-vertex triangle. Its corners are shared with
  the head, both cape panels and the chest; adjacent boundaries meet exactly.
- Luciano's viewer-left wing is a triangle. The viewer-right wing is a convex
  quadrilateral, split from the blue area beneath it. That split has a shared
  edge, and wing attachment points are shared with neighbouring pieces.

These are interpretations guided by the user's descriptions, recorded in JSON.
They are not new automatic detections. The raw detected scene remains available,
and the recipe can be inspected, changed, or omitted without retracing the photo.
Shape IDs and source-region references survive where a shape is replaced.

`study_scene.py` owns the typed scene format. `shape_edits.py` exposes small tools
an agent can call without loading OpenCV or a pose model:

```sh
uv run --no-project shape_edits.py inspect output/shapes/altus.json --shape region-160-0
uv run --no-project shape_edits.py schema
uv run --no-project shape_edits.py apply output/shapes/altus-detected.json \
  --plan edits/altus.json --output /tmp/altus-corrected.json
```

The available operations define/move shared anchors, scale strokes, replace a
polygon, splice vertices and split a polygon into independently named pieces.
For example, moving `collar-tip` updates all four attached vertices:

```json
{
  "id": "raise-collar-tip",
  "scene": "Altus",
  "description": "Move the shared collar/cape/chest point upward.",
  "operations": [
    {"op": "move_anchor", "id": "collar-tip", "point": [181.11, 195]}
  ]
}
```

Plans are applied to a copy and validated before writing. Missing shapes,
invalid geometry and broken shared points are rejected. Replaying the identical
plan is a no-op, so stroke widths do not accumulate. Changing an already-applied
plan requires replaying from `*-detected.json`; replacing a bound shape cannot
silently discard its shared anchors.

This is an experimental CLI and a shared-vertex constraint, not a general
constraint solver, an MCP service or a native canvas feature. Future edits can
extend the operation set while retaining explicit provenance.

Validation uses the repository harness:

```sh
uv run harness test unit -- tests/unit/test_photo_shape_edits.py -q
uv run harness test frontend -- tests/frontend/test_photo_vector_study.py -q
```

The browser check opens the tracked gallery, checks images, selection, exploded
view and overflow, and writes desktop/phone screenshots to
`/tmp/photo-vector-study-checks/`. After regeneration, run
`uv run --no-project package_study.py` before committing the review assets.

The next character-generation experiment and the proposed 1,000-example dataset
are recorded in [NEXT_EXPERIMENT.md](NEXT_EXPERIMENT.md).

## Guided regularization and retained contours

The intended upload-and-guidance workflow is recorded in
[INTERACTION.md](INTERACTION.md). The regularizer is now an actual deterministic
function, separate from the explicitly positioned collar edit:

- `regularize_polygon` chooses the requested vertex count by removing
  low-contribution corners, without removing pinned/shared vertices.
- Unpinned triangle sides are refitted to their original contour runs.
- Trapezoid fitting makes a selected pair of opposite edges parallel.
- Boundary error and area-change limits reject excessive simplification.

`edits/altus-regularize.json` applies these priors to the three red feathers,
both blade faces and the seven-sided left cape. The hem corners are protected.
The exported scene records each fit's error and area change. A five-sided cape
candidate that loses the marked detail is deliberately rejected by the check.

Tacito now has a separate retained-contour variant. `retained_tacito.py` keeps
the first extraction's detailed colour boundaries and authors a complete sword
behind the character, including one continuous blade ridge. Sword geometry and
the region classification are manual interpretations; the remaining contours
come from the extraction. `wolf-postprocessed.svg/json` preserve the earlier
uniform-stroke alternative. The first extraction remains directly linked and
labelled as the preferred reference.
