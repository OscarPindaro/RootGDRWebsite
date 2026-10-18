# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#   "dghs-imgutils==0.19.0", "onnxruntime==1.23.2", "numpy==1.26.4",
#   "opencv-contrib-python==4.11.0.86", "pillow==12.0.0", "pydantic==2.12.5",
#   "huggingface-hub==0.36.0",
# ]
# ///
"""Run the actual dghs-imgutils anime pose API on the same OpenCV crops."""

from pathlib import Path

from imgutils.pose import dwpose_estimate
from PIL import Image, ImageDraw
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent
LINKS = [
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 4),
    (1, 5),
    (5, 6),
    (6, 7),
    (1, 8),
    (8, 9),
    (9, 10),
    (1, 11),
    (11, 12),
    (12, 13),
    (0, 14),
    (14, 16),
    (0, 15),
    (15, 17),
]


class Trial(BaseModel):
    character: str
    mode: str
    image_width: int
    image_height: int
    # The package returns OpenPose18 body indices followed by feet/face/hands.
    poses: list[list[tuple[float, float, float]]]
    error: str | None = None


class Report(BaseModel):
    model: str = "dghs-imgutils 0.19.0 / yzd-v/DWPose / dw-ll_ucoco_384.onnx"
    coordinates: str = "Crop pixels; each point is x, y, model score."
    trials: list[Trial]


def main() -> None:
    output = ROOT / "output" / "dwpose"
    output.mkdir(parents=True, exist_ok=True)
    report = Report(trials=[])
    inputs = [
        (slug, ROOT / "output/opencv" / f"{slug}-isolated.png")
        for slug in ("altus", "luciano", "wolf")
    ]
    inputs.append(("control", ROOT / ".cache/pose-positive-control.jpg"))
    for slug, path in inputs:
        image = Image.open(path).convert("RGB")
        for mode in ("detected", "crop-assisted"):
            if slug == "control" and mode == "crop-assisted":
                continue
            trial = Trial(
                character=slug,
                mode=mode,
                image_width=image.width,
                image_height=image.height,
                poses=[],
            )
            try:
                poses = dwpose_estimate(image, auto_detect=mode == "detected")
                trial.poses = [
                    [tuple(map(float, point)) for point in pose.all] for pose in poses
                ]
            except (ValueError, RuntimeError) as error:
                # Preserve a package/model failure as a failure, not "no detection".
                trial.error = str(error)
            overlay = image.copy()
            ink = ImageDraw.Draw(overlay)
            for pose in trial.poses:
                for a, b in LINKS:
                    if pose[a][2] >= 0.3 and pose[b][2] >= 0.3:
                        color = "#009cd1" if a in (2, 3, 8, 9) else "#e84b63"
                        ink.line([pose[a][:2], pose[b][:2]], fill=color, width=3)
                for x, y, score in pose[:18]:
                    if score >= 0.3:
                        ink.ellipse((x - 3, y - 3, x + 3, y + 3), fill="#27ac70")
            overlay.save(output / f"{slug}-{mode}.png")
            report.trials.append(trial)
            print(
                f"{slug} {mode}: {len(trial.poses)} poses; error={trial.error}",
                flush=True,
            )
            (output / "results.json").write_text(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
