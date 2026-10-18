# Pose estimation on abstract drawn characters — literature notes

Research notes for later, recorded 2026-10-18. This documents what the
literature says about fine-tuning a pose estimator for a small set of
hand-drawn, abstract characters, and about data augmentation. It is a
reference, not a plan and not a claim that any model is trained.

Context: ten hand-drawn samples (photographed raster, not vector), no synthetic
generator yet, sometimes capes occlude the body. The vector/rig scripts in this
study are the in-progress reconstruction of those drawings into vector geometry,
not an existing asset. The baseline is weak, mostly because of the cape
occlusion and the photo-to-drawing domain gap.

## Verdict in one paragraph

Ten samples cannot train a pose estimator by themselves; a frozen backbone
with a new head on ten images overfits to those ten. The real obstacle is the
domain gap between real photos and the drawings, and the cape occlusion, not
the architecture. The proven path is synthetic data in the target style plus
a short fine-tune, using the ten real drawings as a style/personalization
anchor rather than the training set. Heavy keypoint-consistent augmentation
helps geometric robustness but is not a substitute for synthetic diversity,
and it does not fix occlusion.

## Observed baseline (this study)

- MediaPipe Pose Landmarker (README, `pose_probe.py`): at 0.5 threshold all six
  inputs return zero poses; at 0.25 only Luciano's crop returns one pose, and
  its limb landmarks land inside the torso instead of following wings/feet.
- HumanArt RTMPose-l + YOLOX-m (`humanart_probe.py`): detects and returns a
  skeleton on the crops, but joints are frequently wrong where a cape covers
  the torso/hips. A returned skeleton with high scores does not mean correct
  joints.
- DWPose and the Bizarre (WACV) model are probed separately
  (`dwpose_probe.py`, `bizarre_probe.py`, `compare_poses.py`).

The cape is the recurring failure: it is a large occlusion over the most
informative keypoints (torso, hips, sometimes thighs), and that is exactly the
failure mode the occlusion literature says augmentation cannot repair.

## Domain gap is larger than the sample problem

Photo-trained models transfer poorly to illustrations. Concrete numbers:

- Human-Art benchmark (CVPR 2023), RTMPose-T on the Human-Art validation set:
  - `rtmpose-t-coco` (photos only): AP 0.161.
  - `rtmpose-t-humanart-coco` (photos + art): AP 0.249.
  A ~55% relative gain from adding art data to the same architecture. Human-Art
  is 50k images / 123k person instances across 20 scenarios (5 natural + 15
  artificial: paintings, sculpture, cartoons, sketches, 3D renders).

- WACV 2022 "Transfer Learning for Pose Estimation of Illustrated Characters"
  (Chen & Zwicker) reports out-of-the-box generalization to illustrations:
  - OpenPose: OKS@50 0.4922 (poor).
  - Mask R-CNN: OKS@50 0.7584 (much better, less overfit to photos).
  This matters for tooling choice: OpenPose-style bottom-up models generalize
  worse than Mask-R-CNN-style top-down models to drawings.

## The recipe that works: synthetic data + short fine-tune

- Khungurn & Chou (MANPU/ICPR 2016), "Pose estimation of anime/manga
  characters: a case for synthetic data": pretrain on a large synthetic set
  (1M frames rendered from MikuMikuDance 3D models and mocaps), then fine-tune
  on a small set of real drawings (~2k). Their synthetic MMD data is not
  public, which is why the WACV work retargeted the problem.
- Meta's Amateur Drawings project (~180k annotated drawings): repurpose
  photo-trained models for detection/segmentation/pose, then fine-tune on the
  drawings domain. Meta's own warning: style-transfer synthetic data does not
  capture paper creases, erased lines, glare, shadows. That caveat applies here,
  because these inputs are photographs of hand drawings, not clean digital lines.

The synthetic route in this study is a goal, not a given. The characters are
hand-drawn raster photographs; `openpose_rig.py`, `body_skin.py` and
`body_surface.py` are the reconstruction attempts that turn them into vector
geometry with an explicit rig. Re-articulating that rig would yield ground-truth
joints, but only once the reconstruction is good enough to author and re-pose.
`NEXT_EXPERIMENT.md` records that plan (scale toward 1,000 generated examples,
keep joint presence/visibility/occlusion separate), but it depends on the
vector reconstruction succeeding first.

## The WACV transfer-learning result (read in full)

Chen & Zwicker upgraded Khungurn's AnimeDrawingsDataset (2k -> 4k images, all
17 COCO keypoints + boxes) and trained without synthetic data. Their findings:

- A domain-specific backbone (ResNet50 trained as a Danbooru tagger on 837k
  images / 1062 classes) carries more predictive power than a task-specific
  Mask R-CNN pretrained on COCO keypoints.
  - "Task Fine-tuning Only" (frozen Mask R-CNN backbone, new head): OKS@50 0.8026.
  - "Domain Features Only" (frozen tagger backbone + keypoint head): 0.8607.
  - Feature concatenation of both: 0.8982; feature matching: 0.8953 at 9.9M
    params, 8.8x more parameter-efficient, ~1/3 faster.
- Augmentation for the pose model: random rotation (full 360 deg allowed),
  translation, scaling, flipping with left-right keypoint swap, recoloring.
- Training: Adam lr 1e-3, batch 32, 1000 epochs.
- Adversarial domain adaptation (DeepFashion2 / COCO) was unstable and
  performed worse (NaN loss at epoch 795 / 354). Avoid adversarial DA; it is
  fragile.
- Metric caveat: COCO OKS sigmas are calibrated for natural-human annotation
  disagreement; illustrated proportions (bigger head/eyes, hair, clothing)
  loosen the normalized thresholds. Compare to your own annotated holdout,
  not to COCO absolute numbers.

## Augmentation recipe (what people actually use)

All keypoint transforms must apply the same affine matrix to the image and the
keypoints; libraries `imgaug`, `albumentations`, or MMPose pipelines do this
correctly. Left-right flips must swap the left/right keypoint indices.

Standard HRNet/MMPose defaults (from the occlusion paper's Table I and the
HRNet pipeline):

- Random rotation within [-45, 45] degrees (the WACV illustration model allows
  full 360 degrees).
- Random scale in [0.65, 1.35].
- Horizontal flip.
- Half-body augmentation with probability ~0.3: crop to upper or lower body
  and drop the out-of-view keypoints.
- Recoloring (color jitter), background compositing, random translation/crop.

Effect size, from the occlusion paper (HRNet on COCO val, mAP):

- No augmentation: 65.3.
- + flip + rotation + scale: 73.9 (+8.6, the big win).
- + half-body: 74.3 (+0.4).
- Targeted occlusion augmentations (blur, cutout, PartMix): at most ~0.2 gain,
  often neutral or harmful.

Conclusion to carry forward: the geometric triplet (flip + rotate + scale) is
where augmentation pays off. Additional occlusion augmentations are marginal.

## Capes / occlusion — the honest caveat

"Tilting at windmills" (Pytel et al., ICPR 2020) is the key negative result:

- Pose estimators are not robust to occlusion, and occlusion-specific data
  augmentation does not solve occlusion. Part-level occlusion (a rectangle over
  a whole part) hurts far more than keypoint-level occlusion; blacking out the
  upper body drops mAP by >44%, and sides by ~24% each.
- Occluding the nose is the most damaging single-keypoint attack (~5% mAP drop,
  and it degrades the eyes by ~10% because they are spatially close).

A cape is closest to a part-level occlusion over the torso/hips. Expect any
trained model to be weakest exactly there, and do not expect augmentation to
fix it. The practical mitigations are:

1. Label capes as an occlusion layer with per-joint visibility, and evaluate
   visible and occluded joints separately (already in `NEXT_EXPERIMENT.md`).
2. Generate synthetic cape/occlusion variants explicitly (capes, held objects,
   arms crossing the torso) so the model at least learns "joint hidden here".
3. Keep a separate "hard" test set of cape-heavy drawings; do not tune on it.

## What ten samples can actually support

- They cannot be a training set for fine-tuning a full keypoint head.
- They can be a personalization/style-anchor set mixed into a synthetic train
  split, and a small held-out validation set.
- They can seed a few-shot keypoint detection approach: methods that take a
  handful of support images + keypoints and detect the same keypoints in a new
  image with no fine-tuning (Detect Any Keypoints, AAAI 2024; ESCAPE, CVPR
  2024; FSKD). These are worth trying before training anything.

## Recommended experiment order (when synthetic data exists)

1. Baseline already run (MediaPipe, HumanArt RTMPose, DWPose, Bizarre).
2. Generate 1,000+ rig-rendered samples in this style with per-joint
   visibility, per `NEXT_EXPERIMENT.md`.
3. Fine-tune RTMPose (frozen backbone, new head, small LR, few epochs) on
   synthetic + the ten real drawings, with the flip/rotate/scale augmentation
   recipe.
4. Evaluate visible and occluded joints separately, on drawings outside the
   generated style and on the cape-heavy holdout.
5. Compare against the pretrained checkpoint and a geometry-based fitter; a
   thousand images is an experiment, not proof of a general estimator.

## Sources

- Khungurn & Chou, "Pose estimation of anime/manga characters: a case for
  synthetic data" (2016). https://gwern.net/doc/anime/2016-khungurn.pdf
- Chen & Zwicker, "Transfer Learning for Pose Estimation of Illustrated
  Characters" (WACV 2022). arXiv:2108.01819,
  https://github.com/ShuhongChen/bizarre-pose-estimator
- Ju et al., "Human-Art" (CVPR 2023). arXiv:2303.02760,
  https://github.com/IDEA-Research/HumanArt
- Pytel et al., "Tilting at windmills: Data augmentation for deep pose
  estimation does not help with occlusions" (ICPR 2020). arXiv:2010.10451
- Meta, "A new, unique AI dataset for animating amateur drawings" (2023).
  https://ai.meta.com/blog/ai-dataset-animation-drawings/
  (paper arXiv:2303.12741, code https://github.com/facebookresearch/AnimatedDrawings)
- Keras, "Keypoint Detection with Transfer Learning" (StanfordExtra dogs).
  https://keras.io/examples/vision/keypoint_detection/
- "Detect Any Keypoints" (AAAI 2024). https://doi.org/10.1609/aaai.v38i4.28180
- "ESCAPE" few-shot category-agnostic pose (CVPR 2024).
  https://doi.org/10.1109/cvpr52733.2024.02217
