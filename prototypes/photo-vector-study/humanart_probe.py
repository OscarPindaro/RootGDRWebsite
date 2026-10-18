# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#   "rtmlib==0.0.16", "onnxruntime==1.23.2", "numpy==1.26.4",
#   "opencv-python==4.11.0.86", "opencv-contrib-python==4.11.0.86",
#   "pillow==12.0.0", "pydantic==2.12.5",
# ]
# ///
"""Probe illustrated-character pose models against the OpenCV crops.

Both models below were released for HumanArt. This does not use the hand-authored
polygon geometry, and does not alter or correct model-predicted joints.
"""

import argparse
import hashlib
from pathlib import Path
from typing import Literal
from urllib.request import urlretrieve
from zipfile import ZipFile

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
from pydantic import BaseModel, Field
from rtmlib import RTMPose, YOLOX, draw_skeleton

ROOT = Path(__file__).resolve().parent
DETECTOR_URL = "https://download.openmmlab.com/mmpose/v1/projects/rtmposev1/onnx_sdk/yolox_m_8xb8-300e_humanart-c2c7a14a.zip"
POSE_URL = "https://download.openmmlab.com/mmpose/v1/projects/rtmposev1/onnx_sdk/rtmpose-l_8xb256-420e_humanart-256x192-389f2cb0_20230611.zip"
JOINT_NAMES = (
    "nose",
    "left_eye",
    "right_eye",
    "left_ear",
    "right_ear",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
)
CHARACTERS = [("altus", "Altus"), ("luciano", "Luciano"), ("wolf", "Tacito")]


class Joint(BaseModel):
    name: str
    x: float
    y: float
    score: float


class Trial(BaseModel):
    character: str
    variant: str
    mode: Literal["detected", "crop-assisted"]
    image_width: int
    image_height: int
    boxes: list[tuple[float, float, float, float]]
    poses: list[list[Joint]]
    overlay: str


class ModelSource(BaseModel):
    url: str
    sha256: str


class Report(BaseModel):
    detector: ModelSource
    pose_model: ModelSource
    detector_threshold: float = 0.3
    display_joint_threshold: float = 0.3
    coordinates: str = "Pixels in the corresponding OpenCV crop; raw model predictions."
    note: str = (
        "Crop-assisted trials bypass detection and always request a pose for the "
        "whole crop. A returned skeleton and high scores do not establish correctness."
    )
    trials: list[Trial] = Field(default_factory=list)


def download_model(url: str, cache: Path) -> tuple[Path, ModelSource]:
    archive = cache / url.rsplit("/", 1)[1]
    model = archive.with_suffix(".onnx")
    if not model.exists():
        if not archive.exists():
            print(f"Downloading {archive.name}", flush=True)
            urlretrieve(url, archive)
        with ZipFile(archive) as bundle:
            members = [p for p in bundle.namelist() if p.endswith(".onnx")]
            if len(members) != 1:
                raise ValueError(
                    f"Expected one ONNX model in {archive.name}: {members}"
                )
            model.write_bytes(bundle.read(members[0]))
    return model, ModelSource(
        url=url, sha256=hashlib.sha256(model.read_bytes()).hexdigest()
    )


def gallery(output: Path, report: Report) -> None:
    cards = []
    for slug, name in CHARACTERS:
        trials = [
            t for t in report.trials if t.character == slug and t.variant == "isolated"
        ]
        if not trials:
            continue
        figures = []
        for trial in trials:
            label = (
                f"Rilevamento automatico · {len(trial.poses)} pose"
                if trial.mode == "detected"
                else "Posa richiesta sul ritaglio OpenCV"
            )
            figures.append(
                f'<figure><a href="{trial.overlay}" target="_blank">'
                f'<img src="{trial.overlay}" alt="{name}: {label}"></a>'
                f"<figcaption>{label}</figcaption></figure>"
            )
        cards.append(
            f"<article><h2>{name}</h2><div class='figures'>{''.join(figures)}</div></article>"
        )
    html = """<!doctype html><html lang="it"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pose su illustrazioni · HumanArt</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f4f0e5;color:#302d2b;font:16px/1.6 system-ui}
main{max-width:1250px;margin:auto;padding:30px}h1{font:42px Georgia,serif}h2{font:28px Georgia,serif}
p{max-width:900px}article{border-top:1px solid #c9bfac;margin-top:24px}
.figures{display:grid;grid-template-columns:1fr 1fr;gap:24px}figure{margin:0}
img{width:100%;height:610px;object-fit:contain}figcaption{text-align:center}
a{color:#365b70;display:inline-flex;align-items:center;min-height:44px}
figure a{display:block}a:focus-visible{outline:3px solid #008ed0;outline-offset:4px}
@media(max-width:650px){main{padding:20px 14px}.figures{gap:8px}img{height:360px}figcaption{font-size:12px}}
</style><main>
<p>Root GDR · studio 03</p><h1>Un modello allenato sulle illustrazioni.</h1>
<p>RTMlib con YOLOX-m e RTMPose-l, entrambi nelle versioni HumanArt.
A sinistra il modello deve trovare il personaggio; a destra riceve il ritaglio
prodotto da OpenCV. Nessun punto dello scheletro è stato corretto a mano.</p>
<p>I punti con punteggio inferiore a 0,3 sono nascosti nella figura, ma restano
nel JSON. Un punteggio alto non garantisce che un’articolazione sia al posto giusto.</p>
<p><a href="results.json">Coordinate e punteggi</a> ·
<a href="comparison.png" target="_blank">Confronto PNG</a> ·
<a href="../study.zip" download>Scarica risultati e codice</a> ·
<a href="../pose-comparison/">Confronto con DWPose e Bizarre</a> ·
<a href="../opencv/">Esperimento OpenCV</a></p>
CARDS
</main></html>""".replace("CARDS", "".join(cards))
    (output / "index.html").write_text(html)

    board = Image.new("RGB", (1440, 1030), "#f4f0e5")
    ink = ImageDraw.Draw(board)
    font_path = "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf"
    title = ImageFont.truetype(font_path, 30)
    small = ImageFont.truetype(font_path, 18)
    ink.text(
        (30, 20),
        "RTMPose HumanArt · pose proposte sul ritaglio OpenCV",
        font=title,
        fill="#302d2b",
    )
    ink.text(
        (30, 75),
        "Coordinate del modello, senza correzioni manuali · punti mostrati se score ≥ 0,3",
        font=small,
        fill="#786e61",
    )
    for index, (slug, name) in enumerate(CHARACTERS):
        path = output / f"{slug}-isolated-crop-assisted.png"
        if not path.exists():
            continue
        image = ImageOps.contain(Image.open(path), (440, 790))
        board.paste(
            image,
            (
                30 + index * 470 + (440 - image.width) // 2,
                130 + (790 - image.height) // 2,
            ),
        )
        ink.text((30 + index * 470, 950), name, font=title, fill="#302d2b")
    board.save(output / "comparison.png")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "output" / "opencv")
    parser.add_argument("--output", type=Path, default=ROOT / "output" / "humanart")
    parser.add_argument("--cache", type=Path, default=ROOT / ".cache" / "humanart")
    args = parser.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    args.output.mkdir(parents=True, exist_ok=True)
    detector_path, detector_source = download_model(DETECTOR_URL, args.cache)
    pose_path, pose_source = download_model(POSE_URL, args.cache)
    detector = YOLOX(
        str(detector_path),
        model_input_size=(640, 640),
        score_thr=0.3,
        backend="onnxruntime",
        device="cpu",
    )
    estimator = RTMPose(
        str(pose_path), model_input_size=(192, 256), backend="onnxruntime", device="cpu"
    )
    report = Report(detector=detector_source, pose_model=pose_source)
    inputs = [
        (slug, variant, args.input / f"{slug}-{variant}.png")
        for slug, _ in CHARACTERS
        for variant in ("rectified", "isolated")
    ]
    control = ROOT / ".cache" / "pose-positive-control.jpg"
    if control.exists():
        inputs.append(("control", "human-photo", control))
    for slug, variant, path in inputs:
        image = cv2.imread(str(path))
        if image is None:
            raise ValueError(f"Cannot read {path}")
        height, width = image.shape[:2]
        detected = detector(image)
        for mode in ("detected", "crop-assisted"):
            if slug == "control" and mode == "crop-assisted":
                continue
            boxes = (
                detected if mode == "detected" else np.float32([[0, 0, width, height]])
            )
            overlay = image.copy()
            poses = []
            # RTMlib falls back to the full image when bboxes=[], so explicitly skip
            # pose inference after failed detection. The crop-assisted trial is separate.
            if len(boxes):
                keypoints, scores = estimator(image, bboxes=boxes)
                for points, confidence in zip(keypoints, scores, strict=True):
                    poses.append(
                        [
                            Joint(
                                name=name,
                                x=float(point[0]),
                                y=float(point[1]),
                                score=float(score),
                            )
                            for name, point, score in zip(
                                JOINT_NAMES, points, confidence, strict=True
                            )
                        ]
                    )
                overlay = draw_skeleton(overlay, keypoints, scores, kpt_thr=0.3)
            for x0, y0, x1, y1 in boxes:
                cv2.rectangle(
                    overlay,
                    (int(x0), int(y0)),
                    (int(x1) - 1, int(y1) - 1),
                    (100, 170, 70),
                    1,
                )
            filename = f"{slug}-{variant}-{mode}.png"
            cv2.imwrite(str(args.output / filename), overlay)
            report.trials.append(
                Trial(
                    character=slug,
                    variant=variant,
                    mode=mode,
                    image_width=width,
                    image_height=height,
                    boxes=boxes.tolist() if len(boxes) else [],
                    poses=poses,
                    overlay=filename,
                )
            )
            confident = [sum(j.score >= 0.3 for j in pose) for pose in poses]
            print(
                f"{slug} {variant} {mode}: {len(poses)} poses; joints ≥0.3: {confident}",
                flush=True,
            )
    (args.output / "results.json").write_text(report.model_dump_json(indent=2))
    gallery(args.output, report)


if __name__ == "__main__":
    main()
