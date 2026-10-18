# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = ["mediapipe==0.10.21", "pillow==12.0.0", "pydantic==2.12.5"]
# ///
"""Measure MediaPipe's response to the original photos and character crops."""

import argparse
from pathlib import Path

import mediapipe as mp
import numpy as np
from PIL import Image, ImageDraw, ImageOps
from pydantic import BaseModel

from drawings import DRAWINGS


class Landmark(BaseModel):
    name: str
    x: float
    y: float
    z: float
    visibility: float
    presence: float


class PoseTrial(BaseModel):
    character: str
    input_kind: str
    threshold: float
    poses: list[list[Landmark]]


class PoseReport(BaseModel):
    model: str = "MediaPipe Pose Landmarker Full, float16, version 1"
    coordinates: str = "Normalized to the trial image, not the original photo."
    trials: list[PoseTrial]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--photos", type=Path, nargs=3, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "output")
    parser.add_argument("--processed-dir", type=Path)
    parser.add_argument("--character", choices=["altus", "luciano", "wolf"])
    parser.add_argument(
        "--control", type=Path, help="Optional human photo to verify the model."
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    report = PoseReport(trials=[])
    control_pending = args.control is not None
    for threshold in (0.5, 0.25):
        options = mp.tasks.vision.PoseLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(args.model)),
            running_mode=mp.tasks.vision.RunningMode.IMAGE,
            min_pose_detection_confidence=threshold,
            min_pose_presence_confidence=threshold,
            num_poses=1,
        )
        with mp.tasks.vision.PoseLandmarker.create_from_options(options) as detector:
            for drawing, photo in zip(DRAWINGS, args.photos, strict=True):
                if args.character and drawing.slug != args.character:
                    continue
                original = ImageOps.exif_transpose(Image.open(photo)).convert("RGB")
                if args.processed_dir:
                    rectified = Image.open(
                        args.processed_dir / f"{drawing.slug}-rectified.png"
                    ).convert("RGB")
                    isolated = Image.open(
                        args.processed_dir / f"{drawing.slug}-isolated.png"
                    ).convert("RGB")
                    inputs = [
                        ("rectified", rectified),
                        ("isolated", isolated),
                        (
                            "padded",
                            ImageOps.expand(
                                isolated,
                                border=round(max(isolated.size) * 0.15),
                                fill="white",
                            ),
                        ),
                    ]
                else:
                    inputs = [
                        ("photo", original),
                        ("crop", original.crop(drawing.crop)),
                    ]
                if control_pending:
                    inputs.append(
                        ("human-control", Image.open(args.control).convert("RGB"))
                    )
                    control_pending = False
                for kind, image in inputs:
                    result = detector.detect(
                        mp.Image(
                            image_format=mp.ImageFormat.SRGB,
                            data=np.asarray(image),
                        )
                    )
                    trial = PoseTrial(
                        character="control"
                        if kind == "human-control"
                        else drawing.slug,
                        input_kind=kind,
                        threshold=threshold,
                        poses=[
                            [
                                Landmark(
                                    name=mp.solutions.pose.PoseLandmark(i).name,
                                    x=p.x,
                                    y=p.y,
                                    z=p.z,
                                    visibility=p.visibility,
                                    presence=p.presence,
                                )
                                for i, p in enumerate(pose)
                            ]
                            for pose in result.pose_landmarks
                        ],
                    )
                    report.trials.append(trial)
                    print(
                        f"{trial.character} {kind} threshold={threshold}: {len(trial.poses)} pose(s)"
                    )
                    if trial.poses:
                        overlay = image.copy()
                        ink = ImageDraw.Draw(overlay)
                        for pose in trial.poses:
                            for a, b in mp.solutions.pose.POSE_CONNECTIONS:
                                ink.line(
                                    [
                                        (
                                            pose[j].x * image.width,
                                            pose[j].y * image.height,
                                        )
                                        for j in (a, b)
                                    ],
                                    fill="#f13bbd",
                                    width=3,
                                )
                            for p in pose:
                                x, y = p.x * image.width, p.y * image.height
                                ink.ellipse(
                                    (x - 3, y - 3, x + 3, y + 3), fill="#35e6c3"
                                )
                        overlay.save(
                            args.output / f"{drawing.slug}-pose-{kind}-{threshold}.png"
                        )
    (args.output / "pose-results.json").write_text(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
