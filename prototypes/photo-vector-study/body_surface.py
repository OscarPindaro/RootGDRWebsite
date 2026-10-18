"""Shoulder-based torso/limb intersections and visible foreground arm edges.

Construction surfaces are computational inputs. Only their joined boundary and
the explicitly visible occlusion edges are rendered as the body's artwork.
"""

from typing import Literal

from pydantic import BaseModel, Field
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPoint,
    Point as GPoint,
    Polygon as GPolygon,
)
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from body_skin import Pose, SkinTarget, TorsoSection, sample_rig, unit
from head_attachment import attach_head
from study_scene import Compound, Point, Polygon, Scene, ShapeStyle


class Component(BaseModel):
    id: str
    outline: list[Point]


class Crossing(BaseModel):
    arm: str
    point: Point
    ring: Literal["outer", "hole"]


class OcclusionEdge(BaseModel):
    arm: str
    points: list[Point]


class SurfaceTarget(SkinTarget):
    format: Literal["intersection-skin-target"] = "intersection-skin-target"
    body_holes: list[list[Point]] = Field(default_factory=list)
    components: list[Component]
    crossings: list[Crossing]
    occlusion_edges: list[OcclusionEdge]
    reference_markers: dict[str, Point] = Field(default_factory=dict)
    foreground_arms: list[str]
    method: str = "Shoulder-based torso, bisector limb surfaces, geometric union and clipped foreground edges."


def points_in(geometry: BaseGeometry) -> list[Point]:
    if isinstance(geometry, GPoint):
        return [(geometry.x, geometry.y)]
    if isinstance(geometry, (MultiPoint, GeometryCollection)):
        return [point for child in geometry.geoms for point in points_in(child)]
    return []


def lines_in(geometry: BaseGeometry) -> list[list[Point]]:
    if isinstance(geometry, LineString):
        return [list(geometry.coords)] if geometry.length > 1e-7 else []
    if isinstance(geometry, (MultiLineString, GeometryCollection)):
        return [line for child in geometry.geoms for line in lines_in(child)]
    return []


def build_surface(
    pose: Pose,
    *,
    foreground_arms: tuple[str, ...] = ("R", "L"),
) -> tuple[Scene, SurfaceTarget]:
    rig = sample_rig(pose)
    joints, sections = rig.joints, rig.sections
    torso_sections = []
    # Upper torso joins the outer shoulder flesh points, not the inner roots
    # previously forced to act as armpits. Intersections determine the joins.
    left_shoulder = sections["RShoulder"].left
    right_shoulder = sections["LShoulder"].right
    if pose.torso:
        top = joints["Neck"]
        bottom = tuple((a + b) / 2 for a, b in zip(joints["RHip"], joints["LHip"]))
        dx, dy = bottom[0] - top[0], bottom[1] - top[1]
        tangent = unit((dx, dy))
        lateral = tangent[1], -tangent[0]
        for name, station in (("chest", pose.torso.chest), ("waist", pose.torso.waist)):
            if station is None:
                continue
            center = top[0] + dx * station.height, top[1] + dy * station.height
            wx, wy = lateral[0] * station.half_width, lateral[1] * station.half_width
            torso_sections.append(
                TorsoSection(
                    control=name,
                    height=station.height,
                    half_width=station.half_width,
                    center=center,
                    left=(center[0] - wx, center[1] - wy),
                    right=(center[0] + wx, center[1] + wy),
                )
            )
    torso_outline = [
        left_shoulder,
        right_shoulder,
        *(s.right for s in torso_sections),
        sections["LHip"].right,
        sections["LHip"].left,
        sections["RHip"].right,
        sections["RHip"].left,
        *(s.left for s in reversed(torso_sections)),
    ]
    components = [Component(id="torso", outline=torso_outline)]
    arms: dict[str, GPolygon] = {}
    arm_sides: dict[str, LineString] = {}
    for chain in rig.chains:
        names = chain[1:]
        side = names[0][0]
        arm = names[-1].endswith("Wrist")
        outline = [sections[name].right for name in names]
        if arm:
            outline.append(rig.hand_tips[names[-1]])
        outline.extend(sections[name].left for name in reversed(names))
        id = ("arm-" if arm else "leg-") + side
        components.append(Component(id=id, outline=outline))
        if arm:
            arms[side] = GPolygon(outline)
            # This open path includes upper arm, forearm and hand edges, but
            # deliberately omits the artificial cap across the shoulder root.
            arm_sides[side] = LineString(outline)
    surfaces = [GPolygon(component.outline) for component in components]
    for component, surface in zip(components, surfaces):
        if not surface.is_valid or surface.area <= 1e-7:
            raise ValueError(f"Invalid construction surface: {component.id}")
    joined = unary_union(surfaces)
    if not isinstance(joined, GPolygon) or not joined.is_valid:
        raise ValueError("Construction did not produce one connected, valid body.")
    outer = list(joined.exterior.coords)[:-1]
    holes = [list(ring.coords)[:-1] for ring in joined.interiors]
    torso = surfaces[0]
    crossings = []
    occlusion_edges = []
    for side, arm in arms.items():
        for point in points_in(arm.boundary.intersection(torso.boundary)):
            p = GPoint(point)
            if joined.boundary.distance(p) < 1e-6:
                crossings.append(
                    Crossing(
                        arm=side,
                        point=point,
                        ring="outer" if joined.exterior.distance(p) < 1e-6 else "hole",
                    )
                )
        if side in foreground_arms:
            visible = arm_sides[side].intersection(torso)
            visible = visible.difference(joined.boundary)
            for line in lines_in(visible):
                occlusion_edges.append(OcclusionEdge(arm=side, points=line))
    scene = Scene(
        name=pose.name,
        width=520,
        height=820,
        shapes=[],
        method="Joined shoulder-based torso and bisector limb surfaces",
        interpretation="One body boundary with preserved holes; front arms retain upper-arm and forearm edges.",
    )
    style = ShapeStyle(
        id="body",
        part="body",
        label="Corpo · intersezioni calcolate",
        source_region="surface-union",
        fill=pose.color,
        stroke_width=6,
    )
    if holes:
        scene.shapes.append(Compound(**style.model_dump(), loops=[outer, *holes]))
    else:
        scene.shapes.append(Polygon(**style.model_dump(), kind="polygon", points=outer))
    for index, edge in enumerate(occlusion_edges):
        scene.shapes.append(
            Polygon(
                id=f"arm-front-{index}",
                part="body",
                kind="polyline",
                label="Braccio davanti al torace",
                source_region="clipped-occlusion-edge",
                points=edge.points,
                fill="none",
                stroke_width=4.5,
            )
        )
    head, attachment = attach_head(
        pose.head_kind, pose.color, joints["Neck"], joints["Nose"]
    )
    scene.shapes.extend(head)
    markers = {}
    left_candidates = [
        c.point
        for c in crossings
        if c.arm == "R" and c.ring == "outer" and c.point[1] > joints["Neck"][1] + 10
    ]
    if left_candidates:
        markers["6"] = max(left_candidates, key=lambda p: p[1])
    if torso_sections:
        chest_right = torso_sections[0].right
        if joined.exterior.distance(GPoint(chest_right)) < 1e-6:
            markers["12"] = chest_right
    target = SurfaceTarget(
        width=scene.width,
        height=scene.height,
        pose=pose,
        joints=joints,
        sections=list(sections.values()),
        bones=rig.bones,
        body_vertices=outer,
        vertex_sources=["surface-union"] * len(outer),
        hand_tips=rig.hand_tips,
        head_attachment=attachment,
        torso_sections=torso_sections,
        body_holes=holes,
        components=components,
        crossings=crossings,
        occlusion_edges=occlusion_edges,
        reference_markers=markers,
        foreground_arms=list(foreground_arms),
    )
    return scene, target
