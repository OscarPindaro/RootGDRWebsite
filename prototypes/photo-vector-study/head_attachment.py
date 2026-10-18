"""A head asset follows OpenPose Neck/Nose; it is not part of the skin contour."""

from math import atan2, cos, degrees, hypot, sin
from typing import Literal

from pydantic import BaseModel

from study_scene import Ellipse, Point, Polygon, Shape

HeadKind = Literal["bird", "wolf", "plain"]


class HeadAsset(BaseModel):
    outline: list[Point]
    nose: Point
    eyes: list[Point]


class HeadAttachment(BaseModel):
    part: str = "head"
    anchor: str = "Neck"
    aim: str = "Nose"
    svg_group: str = "head-object"
    pivot: Point
    rotation_degrees: float
    scale: float
    local_asset: HeadAsset
    shape_ids: list[str]


def asset(kind: HeadKind) -> HeadAsset:
    if kind == "bird":
        outline = [(-63, 0), (-69, -126), (109, -53), (125, 5), (99, -24), (61, 0)]
        eyes, nose = [(-27, -85)], (84, -65)
    elif kind == "wolf":
        outline = [
            (-67, 0),
            (-88, -42),
            (-77, -37),
            (-86, -77),
            (-74, -65),
            (-73, -112),
            (-57, -158),
            (-24, -132),
            (31, -132),
            (59, -158),
            (75, -112),
            (81, -77),
            (109, -95),
            (124, -79),
            (117, -25),
            (61, 0),
        ]
        eyes, nose = [(-25, -85), (29, -85)], (120, -87)
    else:
        outline = [(-40, 0), (-54, -58), (-43, -111), (39, -111), (54, -58), (40, 0)]
        eyes, nose = [(-25, -85), (29, -85)], (0, -70)
    # An overlap into the shoulder envelope replaces the previous neck column.
    return HeadAsset(outline=[(x, y - 8) for x, y in outline], nose=nose, eyes=eyes)


def attach_head(
    kind: HeadKind,
    color: str,
    neck: Point,
    nose: Point,
) -> tuple[list[Shape], HeadAttachment]:
    source = asset(kind)
    direction = nose[0] - neck[0], nose[1] - neck[1]
    length = hypot(*direction)
    if length < 1e-8:
        raise ValueError("Neck and Nose cannot coincide for a head attachment.")
    scale = length / hypot(*source.nose)
    angle = atan2(direction[1], direction[0]) - atan2(source.nose[1], source.nose[0])
    c, s = cos(angle), sin(angle)

    def world(point: Point) -> Point:
        x, y = point
        return neck[0] + scale * (c * x - s * y), neck[1] + scale * (s * x + c * y)

    shapes: list[Shape] = [
        Polygon(
            id="head",
            part="head",
            source_region="head-asset",
            label="Testa indipendente",
            kind="polygon",
            points=[world(p) for p in source.outline],
            fill=color,
            stroke_width=6,
        )
    ]
    for index, point in enumerate(source.eyes):
        center = world(point)
        shapes.extend(
            [
                Ellipse(
                    id=f"eye-{index}",
                    part="head",
                    label="Occhio",
                    source_region="head-asset",
                    center=center,
                    radii=(7 * scale, 6 * scale),
                    rotation=degrees(angle),
                    fill="#f4edd8",
                    stroke_width=2.5,
                ),
                Ellipse(
                    id=f"pupil-{index}",
                    part="head",
                    label="Pupilla",
                    source_region="head-asset",
                    center=world((point[0] + 1, point[1])),
                    radii=(2 * scale, 3 * scale),
                    rotation=degrees(angle),
                    fill="#302d2b",
                    stroke_width=1,
                ),
            ]
        )
    shapes.append(
        Ellipse(
            id="nose-mark",
            part="head",
            label="Riferimento Nose",
            source_region="head-asset",
            center=world(source.nose),
            radii=(3 * scale, 2 * scale),
            rotation=degrees(angle),
            fill="#302d2b",
            stroke_width=1,
        )
    )
    attachment = HeadAttachment(
        pivot=neck,
        rotation_degrees=degrees(angle),
        scale=scale,
        local_asset=source,
        shape_ids=[shape.id for shape in shapes],
    )
    return shapes, attachment
