"""A continuous skin outline built from a rig's angle-bisector cross-sections.

No limb rectangles, polygon unions, clothes or objects are rendered. The contour
walk follows the outside of every chain and returns along its inside.
"""

from math import hypot
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from head_attachment import HeadAttachment, HeadKind, attach_head
from openpose_rig import CONNECTIONS, OpenPoseFrame
from shape_edits import validate_scene
from study_scene import Point, Polygon, Scene


class Thickness(BaseModel):
    model_config = ConfigDict(extra="forbid")
    shoulder: float = Field(default=25, gt=0)
    elbow: float = Field(default=18, gt=0)
    wrist: float = Field(default=11, gt=0)
    hand_length: float = Field(default=27, gt=0)
    hip: float = Field(default=24, gt=0)
    knee: float = Field(default=19, gt=0)
    ankle: float = Field(default=10, gt=0)
    toe: float = Field(default=8, gt=0)


class Pose(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    head_kind: HeadKind
    color: str
    openpose: OpenPoseFrame
    thickness: Thickness = Field(default_factory=Thickness)
    overrides: dict[str, float] = Field(default_factory=dict)


class Section(BaseModel):
    joint: str
    center: Point
    bisector: Point
    offset: float
    left: Point
    right: Point
    source_keypoint: str | None = None


class Bone(BaseModel):
    start: str
    end: str
    length: float


class SkinTarget(BaseModel):
    format: Literal["continuous-skin-target"] = "continuous-skin-target"
    version: Literal[2] = 2
    pose_model: Literal["COCO_18"] = "COCO_18"
    width: int
    height: int
    pose: Pose
    joints: dict[str, Point]
    sections: list[Section]
    bones: list[Bone]
    body_vertices: list[Point]
    vertex_sources: list[str]
    hand_tips: dict[str, Point]
    head_attachment: HeadAttachment
    method: str = "One closed contour; two flesh points on each joint's bisector."
    offset_definition: str = (
        "Distance along the bisector, not a miter-corrected perpendicular bone radius."
    )


def unit(vector: Point) -> Point:
    length = hypot(*vector)
    if length < 1e-8:
        raise ValueError("A bone or folded-back joint has no usable direction.")
    return vector[0] / length, vector[1] / length


def cross_section(
    name: str,
    center: Point,
    previous: Point | None,
    following: Point | None,
    offset: float,
) -> Section:
    if offset <= 0:
        raise ValueError("Flesh offset must be positive.")
    directions = []
    if previous is not None:
        directions.append(unit((center[0] - previous[0], center[1] - previous[1])))
    if following is not None:
        directions.append(unit((following[0] - center[0], following[1] - center[1])))
    if not directions:
        raise ValueError("A cross-section requires at least one neighboring bone.")
    tangent = unit((sum(d[0] for d in directions), sum(d[1] for d in directions)))
    bisector = -tangent[1], tangent[0]
    dx, dy = bisector[0] * offset, bisector[1] * offset
    return Section(
        joint=name,
        center=center,
        bisector=bisector,
        offset=offset,
        left=(center[0] + dx, center[1] + dy),
        right=(center[0] - dx, center[1] - dy),
    )


def build_skin(pose: Pose) -> tuple[Scene, SkinTarget]:
    joints = pose.openpose.points()
    geometry = joints.copy()
    sections: dict[str, Section] = {}
    hand_tips = {}
    for side, direction_x in (("L", 1), ("R", -1)):
        wrist, elbow = joints[f"{side}Wrist"], joints[f"{side}Elbow"]
        direction = unit((wrist[0] - elbow[0], wrist[1] - elbow[1]))
        hand_tips[f"{side}Wrist"] = (
            wrist[0] + direction[0] * pose.thickness.hand_length,
            wrist[1] + direction[1] * pose.thickness.hand_length,
        )
        ankle = joints[f"{side}Ankle"]
        geometry[f"{side}FootEnd"] = (
            ankle[0] + direction_x * 28,
            ankle[1] + 14,
        )
    # OpenPose anatomical left is the image-right chain in these frontal examples.
    chains = [
        ["Neck", "LShoulder", "LElbow", "LWrist"],
        ["Neck", "LHip", "LKnee", "LAnkle", "LFootEnd"],
        ["Neck", "RHip", "RKnee", "RAnkle", "RFootEnd"],
        ["Neck", "RShoulder", "RElbow", "RWrist"],
    ]
    radii = {
        "Shoulder": pose.thickness.shoulder,
        "Elbow": pose.thickness.elbow,
        "Wrist": pose.thickness.wrist,
        "Hip": pose.thickness.hip,
        "Knee": pose.thickness.knee,
        "Ankle": pose.thickness.ankle,
        "FootEnd": pose.thickness.toe,
    }
    for chain in chains:
        for index in range(1, len(chain)):
            name, parent = chain[index], chain[index - 1]
            following = geometry[chain[index + 1]] if index + 1 < len(chain) else None
            radius = pose.overrides.get(name, radii[name[1:]])
            sections[name] = cross_section(
                name, geometry[name], geometry[parent], following, radius
            )
            sections[name].source_keypoint = (
                name if name in joints else name[0] + "Ankle"
            )
    bones = [
        Bone(
            start=a,
            end=b,
            length=hypot(joints[b][0] - joints[a][0], joints[b][1] - joints[a][1]),
        )
        for a, b in CONNECTIONS
        if a in joints and b in joints
    ]

    vertices: list[Point] = []
    sources = []
    # The loop closes directly across the shoulder envelope. Between the inner
    # hips it uses one plain segment: no invented central pubic control point.
    for chain in chains:
        for side, names in (
            ("right", chain[1:]),
            ("left", list(reversed(chain[1:]))),
        ):
            if side == "left" and chain[-1].endswith("Wrist"):
                wrist = chain[-1]
                vertices.append(hand_tips[wrist])
                sources.append(wrist + ":tip")
            for name in names:
                section = sections[name]
                vertices.append(section.right if side == "right" else section.left)
                sources.append(name + ":" + side)
    scene = Scene(
        name=pose.name,
        width=520,
        height=820,
        method="Continuous skin from joint bisectors and an explicitly traversed boundary",
        interpretation="COCO_18-driven continuous body; separate head asset, no neck column or pubic point.",
        shapes=[
            Polygon(
                id="body",
                part="body",
                source_region="bisector-skin",
                label="Corpo continuo",
                kind="polygon",
                points=vertices,
                fill=pose.color,
                stroke_width=6,
            )
        ],
    )
    head_shapes, attachment = attach_head(
        pose.head_kind,
        pose.color,
        joints["Neck"],
        joints["Nose"],
    )
    scene.shapes.extend(head_shapes)
    validate_scene(scene)
    target = SkinTarget(
        width=scene.width,
        height=scene.height,
        pose=pose,
        joints=joints,
        sections=list(sections.values()),
        bones=bones,
        body_vertices=vertices,
        vertex_sources=sources,
        hand_tips=hand_tips,
        head_attachment=attachment,
    )
    return scene, target
