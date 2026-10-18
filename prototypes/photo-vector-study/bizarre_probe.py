# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#   "torch==2.5.1+cpu", "torchvision==0.20.1+cpu", "numpy==1.26.4",
#   "pytorch-lightning==1.9.5", "torchmetrics==0.11.4",
#   "pillow==12.0.0", "pydantic==2.12.5", "matplotlib==3.10.1", "setuptools==80.9.0",
#   "kornia==0.6.2",
# ]
# [tool.uv.sources]
# torch = { index = "pytorch-cpu" }
# torchvision = { index = "pytorch-cpu" }
# [[tool.uv.index]]
# name = "pytorch-cpu"
# url = "https://download.pytorch.org/whl/cpu"
# explicit = true
# ///
# SPDX-License-Identifier: AGPL-3.0-only
"""CPU inference study for Bizarre Pose Estimator's feature-matching model.

Inference architecture adapted from Shuhong Chen / Matthias Zwicker:
https://github.com/ShuhongChen/bizarre-pose-estimator
_train/character_pose_estim/models/fermat.py and _util/helper_models_v0.py,
commit b72005c2521c42c34df5c91c3660abab4a86a00c (AGPL-3.0).

Only the training-time Detectron2 teacher is omitted. Every inference weight is
loaded strictly, and raw output is compared with the original forward method.
OpenCV supplies the crop instead of the paper's separate segmenter.
"""

from argparse import Namespace
from collections import OrderedDict
import hashlib
from pathlib import Path
import sys
from typing import NamedTuple

import kornia
import torch
from torch import nn
import torchvision as tv
from torchvision import transforms as T
from torchvision.transforms import functional as TF
from PIL import Image, ImageDraw
from pydantic import BaseModel
from pytorch_lightning.callbacks import ModelCheckpoint

ROOT = Path(__file__).resolve().parent
NAMES = (
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
LINKS = [
    (3, 1),
    (1, 0),
    (0, 2),
    (2, 4),
    (5, 6),
    (5, 7),
    (7, 9),
    (6, 8),
    (8, 10),
    (5, 11),
    (6, 12),
    (11, 12),
    (11, 13),
    (13, 15),
    (12, 14),
    (14, 16),
]


class Features(NamedTuple):
    conv1: torch.Tensor
    layer1: torch.Tensor
    layer2: torch.Tensor
    layer3: torch.Tensor


class Backbone(nn.Module):
    def __init__(self):
        super().__init__()
        base = tv.models.resnet50(weights=None)
        self.conv1, self.bn1, self.relu = base.conv1, base.bn1, base.relu
        self.maxpool = base.maxpool
        self.layer1, self.layer2, self.layer3 = base.layer1, base.layer2, base.layer3
        # Size/normalization verified against the bundled Danbooru tagger.
        self.resize = T.Resize(256, antialias=False)
        self.normalize = T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])

    def forward(self, x: torch.Tensor) -> Features:
        x = self.relu(self.bn1(self.conv1(self.normalize(self.resize(x)))))
        a = self.layer1(self.maxpool(x))
        b = self.layer2(a)
        return Features(x, a, b, self.layer3(b))


class Converter(nn.Module):
    def __init__(self, size: int):
        super().__init__()
        self.resizer = T.Resize(size, antialias=False)
        self.conv1 = nn.Conv2d(64, 64, 1)
        self.layer1 = nn.Conv2d(256, 64, 1)
        self.layer2 = nn.Conv2d(512, 64, 1)
        self.layer3 = nn.Conv2d(1024, 64, 1)
        self.head = nn.Conv2d(256, 128, 3, padding=1, padding_mode="replicate")
        self.relu = nn.LeakyReLU()
        self.batchnorm = nn.BatchNorm2d(256)

    def forward(self, f: Features) -> torch.Tensor:
        converted = torch.cat(
            [
                self.resizer(self.conv1(f.conv1)),
                self.resizer(self.layer1(f.layer1)),
                self.resizer(self.layer2(f.layer2)),
                self.resizer(self.layer3(f.layer3)),
            ],
            dim=1,
        )
        return self.head(self.relu(self.batchnorm(converted)))


class ResidualBlock(nn.Module):
    def __init__(self, channels_in: int, channels: int):
        super().__init__()
        layers = OrderedDict()
        for index in range(3):
            layers[f"conv{index}"] = nn.Conv2d(
                channels_in if index == 0 else channels,
                channels,
                3,
                padding=1,
                padding_mode="replicate",
            )
            layers[f"act{index}"] = nn.ReLU()
            layers[f"norm{index}"] = nn.BatchNorm2d(channels)
        self.net = nn.Sequential(layers)
        self.net_tail = nn.Sequential(
            OrderedDict(
                act3=nn.ReLU(),
                norm3=nn.BatchNorm2d(channels),
            )
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        head = self.net[0](x)
        value = head
        for layer in self.net[1:]:
            value = layer(value)
        return self.net_tail(head + value)


class BizarrePose(nn.Module):
    def __init__(self, size: int):
        super().__init__()
        self.resnet = Backbone()
        self.resizer = T.Resize(size, antialias=False)
        self.keypoint_head = nn.ModuleDict(
            {
                "converter_resnet": Converter(size),
                "matcher_rcnn": nn.Sequential(
                    T.Resize(14, antialias=False),
                    nn.Conv2d(128, 512, 3, padding=1, padding_mode="replicate"),
                    nn.ReLU(),
                    nn.BatchNorm2d(512),
                ),
                "converter_rcnn": nn.Sequential(nn.Conv2d(512, 32, 1), self.resizer),
                "head": nn.Sequential(
                    nn.Conv2d(163, 128, 3, padding=1, padding_mode="replicate"),
                    nn.LeakyReLU(),
                    nn.BatchNorm2d(128),
                    ResidualBlock(128, 64),
                    ResidualBlock(64, 32),
                    nn.Conv2d(32, 25, 3, padding=1, padding_mode="replicate"),
                ),
            }
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        converted = self.resizer(self.keypoint_head["converter_resnet"](self.resnet(x)))
        matched = self.keypoint_head["matcher_rcnn"](converted)
        features = torch.cat(
            [
                self.resizer(x),
                converted,
                self.keypoint_head["converter_rcnn"](matched),
            ],
            dim=1,
        )
        return self.keypoint_head["head"](features)


class Joint(BaseModel):
    name: str
    x: float
    y: float
    heatmap_peak: float


class Trial(BaseModel):
    character: str
    mode: str = "crop-assisted"
    image_width: int
    image_height: int
    joints: list[Joint]


class Report(BaseModel):
    model: str = "Bizarre Pose Estimator feat_match+data"
    checkpoint_url: str = "https://huggingface.co/h54917/bizarre-pose-estimator/resolve/main/bizarre_pose_models.zip"
    checkpoint_sha256: str
    upstream_commit: str = "b72005c2521c42c34df5c91c3660abab4a86a00c"
    max_reference_forward_error: float
    note: str = (
        "OpenCV crop replaces segmentation; no character detector is run. "
        "Heatmap peaks are not calibrated detection confidences. All 17 body "
        "joints are shown, matching the original visualization convention."
    )
    trials: list[Trial]


def main() -> None:
    torch.set_num_threads(4)
    cache = ROOT / ".cache/bizarre"
    output = ROOT / "output/bizarre"
    output.mkdir(parents=True, exist_ok=True)
    with torch.serialization.safe_globals([Namespace, ModelCheckpoint]):
        checkpoint = torch.load(
            cache / "feat_match+data.ckpt",
            map_location="cpu",
            weights_only=True,
        )
    parameters = checkpoint["hyper_parameters"]
    size = parameters["largs"].danbooru_coco.size
    padding = parameters["largs"].danbooru_coco.padding
    model = BizarrePose(parameters["margs"].size).eval()
    inference_weights = {
        key: value
        for key, value in checkpoint["state_dict"].items()
        if not key.startswith("rcnn.")
    }
    model.load_state_dict(inference_weights, strict=True)
    del checkpoint, inference_weights
    # Compare the port against the unmodified original inference forward method.
    sys.path.insert(0, str(cache / "source"))
    from _train.character_pose_estim.models import fermat  # noqa: PLC0415

    torch.manual_seed(0)
    with torch.inference_mode():
        sample = torch.rand(1, 3, size, size)
        expected = fermat.Model.forward(
            model,
            sample,
            smoothing=None,
            return_more=False,
            inference=True,
        )["keypoint_heatmaps"]
        reference_error = float((expected - model(sample)).abs().max())
        if reference_error > 1e-6:
            raise ValueError(f"Reference graph mismatch: {reference_error}")
    report = Report(
        checkpoint_sha256=hashlib.sha256(
            (cache / "feat_match+data.ckpt").read_bytes()
        ).hexdigest(),
        max_reference_forward_error=reference_error,
        trials=[],
    )
    print(
        f"Strict inference weights loaded; reference-forward error={reference_error}",
        flush=True,
    )
    inputs = [
        (slug, ROOT / "output/opencv" / f"{slug}-isolated.png")
        for slug in ("altus", "luciano", "wolf")
    ]
    inputs.append(("anime-control", cache / "source/_samples/megumin.png"))
    for slug, path in inputs:
        image = Image.open(path).convert("RGB")
        side = round(max(image.size) * (1 + padding))
        x0, y0 = round((image.width - side) / 2), round((image.height - side) / 2)
        prepared = TF.resized_crop(
            image,
            y0,
            x0,
            side,
            side,
            (size, size),
            interpolation=T.InterpolationMode.BILINEAR,
        )
        with torch.inference_mode():
            heatmaps = model(TF.to_tensor(prepared)[None]).sigmoid()
            sigma = max(heatmaps.shape[-2:]) * 0.1
            kernel = max(3, int(sigma) * 2 + 1)
            heatmaps = kornia.filters.gaussian_blur2d(
                heatmaps,
                (kernel, kernel),
                (sigma, sigma),
                border_type="reflect",
            )
            values, indices = heatmaps[0, :17].flatten(1).max(dim=1)
        joints = [
            Joint(
                name=name,
                x=float(index % heatmaps.shape[-1]) / heatmaps.shape[-1] * side + x0,
                y=float(index // heatmaps.shape[-1]) / heatmaps.shape[-2] * side + y0,
                heatmap_peak=float(value),
            )
            for name, index, value in zip(NAMES, indices, values, strict=True)
        ]
        overlay = image.copy()
        ink = ImageDraw.Draw(overlay)
        for a, b in LINKS:
            color = "#009cd1" if a in (5, 7, 11, 13) else "#e84b63"
            ink.line(
                [(joints[a].x, joints[a].y), (joints[b].x, joints[b].y)],
                fill=color,
                width=3,
            )
        for joint in joints:
            ink.ellipse(
                (joint.x - 3, joint.y - 3, joint.x + 3, joint.y + 3), fill="#27ac70"
            )
        overlay.save(output / f"{slug}-crop-assisted.png")
        report.trials.append(
            Trial(
                character=slug,
                image_width=image.width,
                image_height=image.height,
                joints=joints,
            )
        )
        print(
            f"{slug}: 17 proposed joints; heatmap peaks {float(values.min()):.3f}–{float(values.max()):.3f}",
            flush=True,
        )
    (output / "results.json").write_text(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
