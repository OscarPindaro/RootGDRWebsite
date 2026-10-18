"""A continuous skin outline built from a rig's angle-bisector cross-sections.

No limb rectangles, polygon unions, clothes or objects are rendered. The contour
walk follows the outside of every chain and returns along its inside.
"""

from math import hypot
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from shape_edits import validate_scene
from study_scene import Ellipse, Point, Polygon, Scene


class Thickness(BaseModel):
    model_config = ConfigDict(extra="forbid")
    neck: float = Field(default=17, gt=0)
    jaw: float = Field(default=17, gt=0)
    shoulder: float = Field(default=25, gt=0)
    elbow: float = Field(default=18, gt=0)
    wrist: float = Field(default=11, gt=0)
    hand: float = Field(default=14, gt=0)
    hip: float = Field(default=24, gt=0)
    knee: float = Field(default=19, gt=0)
    ankle: float = Field(default=10, gt=0)
    toe: float = Field(default=8, gt=0)


class Pose(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    head_kind: Literal["bird", "wolf", "plain"]
    color: str
    joints: dict[str, Point]
    thickness: Thickness = Field(default_factory=Thickness)
    overrides: dict[str, float] = Field(default_factory=dict)


class Section(BaseModel):
    joint: str
    center: Point
    bisector: Point
    offset: float
    left: Point
    right: Point


class Bone(BaseModel):
    start: str
    end: str
    length: float


class SkinTarget(BaseModel):
    format: Literal["continuous-skin-target"] = "continuous-skin-target"
    version: Literal[1] = 1
    width: int
    height: int
    pose: Pose
    joints: dict[str, Point]
    sections: list[Section]
    bones: list[Bone]
    body_vertices: list[Point]
    vertex_sources: list[str]
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
    joints = pose.joints.copy()
    sections: dict[str, Section] = {}
    bones = []
    chains = []
    for side in ("right", "left"):
        wrist, elbow = joints[f"wrist-{side}"], joints[f"elbow-{side}"]
        direction = unit((wrist[0] - elbow[0], wrist[1] - elbow[1]))
        joints[f"hand-{side}"] = (
            wrist[0] + direction[0] * 27,
            wrist[1] + direction[1] * 27,
        )
        ankle = joints[f"ankle-{side}"]
        joints[f"toe-{side}"] = (
            ankle[0] + (28 if side == "right" else -28),
            ankle[1] + 14,
        )
        chains.extend(
            [
                [
                    "neck",
                    f"shoulder-{side}",
                    f"elbow-{side}",
                    f"wrist-{side}",
                    f"hand-{side}",
                ],
                [
                    "pelvis",
                    f"hip-{side}",
                    f"knee-{side}",
                    f"ankle-{side}",
                    f"toe-{side}",
                ],
            ]
        )
    chains = [chains[0], chains[1], chains[3], chains[2]]
    radii = {
        "neck": pose.thickness.neck,
        "jaw": pose.thickness.jaw,
        "shoulder": pose.thickness.shoulder,
        "elbow": pose.thickness.elbow,
        "wrist": pose.thickness.wrist,
        "hand": pose.thickness.hand,
        "hip": pose.thickness.hip,
        "knee": pose.thickness.knee,
        "ankle": pose.thickness.ankle,
        "toe": pose.thickness.toe,
    }
    for chain in chains:
        for index in range(1, len(chain)):
            name, parent = chain[index], chain[index - 1]
            following = joints[chain[index + 1]] if index + 1 < len(chain) else None
            role = name.split("-")[0]
            radius = pose.overrides.get(name, radii[role])
            sections[name] = cross_section(
                name, joints[name], joints[parent], following, radius
            )
            a, b = joints[parent], joints[name]
            bones.append(
                Bone(start=parent, end=name, length=hypot(b[0] - a[0], b[1] - a[1]))
            )
    for name, parent, child in (("neck", "pelvis", "jaw"), ("jaw", "neck", "head")):
        sections[name] = cross_section(
            name,
            joints[name],
            joints[parent],
            joints[child],
            pose.overrides.get(name, radii[name]),
        )
        a, b = joints[parent], joints[name]
        bones.append(
            Bone(start=parent, end=name, length=hypot(b[0] - a[0], b[1] - a[1]))
        )
    a, b = joints["jaw"], joints["head"]
    bones.append(Bone(start="jaw", end="head", length=hypot(b[0] - a[0], b[1] - a[1])))
    a, b = joints["pelvis"], joints["crotch"]
    bones.append(
        Bone(start="pelvis", end="crotch", length=hypot(b[0] - a[0], b[1] - a[1]))
    )
    jaw = sections["jaw"]
    right = jaw.bisector
    down = -right[1], right[0]

    def head_point(x: float, y: float) -> Point:
        return jaw.center[0] + x * right[0] + y * down[0], jaw.center[1] + x * right[
            1
        ] + y * down[1]

    if pose.head_kind == "bird":
        head = [(-63, 0), (-69, -126), (109, -53), (125, 5), (99, -24), (61, 0)]
    elif pose.head_kind == "wolf":
        head = [
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
    else:
        head = [(-40, 0), (-54, -58), (-43, -111), (39, -111), (54, -58), (40, 0)]
    vertices: list[Point] = [jaw.right]
    sources = ["jaw:right"]
    for point in head:
        vertices.append(head_point(*point))
        sources.append("head-profile")
    vertices.extend([jaw.left, sections["neck"].left])
    sources.extend(["jaw:left", "neck:left"])
    # Follow each entire chain along one side, cap it, then return along the
    # opposite side. Root cross-section edges never become interior seams.
    for index, chain in enumerate(chains):
        if index == 2:
            vertices.append(joints["crotch"])
            sources.append("crotch")
        for side, names in (
            ("right", chain[1:]),
            ("left", list(reversed(chain[1:]))),
        ):
            for name in names:
                section = sections[name]
                vertices.append(section.right if side == "right" else section.left)
                sources.append(name + ":" + side)
    vertices.append(sections["neck"].right)
    sources.append("neck:right")
    scene = Scene(
        name=pose.name,
        width=520,
        height=820,
        method="Continuous skin from joint bisectors and an explicitly traversed boundary",
        interpretation="Naked construction study: one body polygon including the attached head and neck.",
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
    # Small facial marks are overlays; they do not split the skin contour.
    eyes = [(-27, -72)] if pose.head_kind == "bird" else [(-25, -77), (29, -77)]
    for index, (x, y) in enumerate(eyes):
        center = head_point(x, y)
        scene.shapes.append(
            Ellipse(
                id=f"eye-{index}",
                part="face",
                label="Occhio",
                source_region="head-profile",
                center=center,
                radii=(7, 6),
                rotation=0,
                fill="#f4edd8",
                stroke_width=2.5,
            )
        )
        scene.shapes.append(
            Ellipse(
                id=f"pupil-{index}",
                part="face",
                label="Pupilla",
                source_region="head-profile",
                center=(center[0] + 1, center[1]),
                radii=(2, 3),
                rotation=0,
                fill="#302d2b",
                stroke_width=1,
            )
        )
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
    )
    return scene, target
