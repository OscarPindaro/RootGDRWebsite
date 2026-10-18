# /// script
# requires-python = ">=3.12"
# dependencies = ["pydantic==2.12.5"]
# ///
"""Inspect and apply replayable user-guided edits to experimental shape scenes."""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from study_scene import (
    AppliedEdit,
    Point,
    Polygon,
    Scene,
    Shape,
    SharedAnchor,
    VertexRef,
)


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AnchorRef(Command):
    anchor: str


Vertex = Point | AnchorRef


class DefineAnchor(Command):
    op: Literal["define_anchor"]
    id: str
    point: Point


class MoveAnchor(Command):
    op: Literal["move_anchor"]
    id: str
    point: Point


class ScaleStrokes(Command):
    op: Literal["scale_strokes"]
    factor: float = Field(gt=0, le=3)


class ReplacePolygon(Command):
    op: Literal["replace_polygon"]
    shape: str
    points: list[Vertex] = Field(min_length=3)
    label: str | None = None


class SpliceVertices(Command):
    op: Literal["splice_vertices"]
    shape: str
    start: int = Field(ge=0)
    delete: int = Field(ge=0)
    points: list[Vertex]


class PolygonPiece(Command):
    id: str
    label: str
    points: list[Vertex] = Field(min_length=3)


class SplitPolygon(Command):
    op: Literal["split_polygon"]
    shape: str
    pieces: list[PolygonPiece] = Field(min_length=2)


Operation = Annotated[
    DefineAnchor
    | MoveAnchor
    | ScaleStrokes
    | ReplacePolygon
    | SpliceVertices
    | SplitPolygon,
    Field(discriminator="op"),
]


class EditPlan(Command):
    id: str
    scene: str | None = None
    description: str
    operations: list[Operation]


class Inspection(BaseModel):
    shape: Shape
    anchors: list[SharedAnchor]


def validate_scene(scene: Scene) -> None:
    shapes = {shape.id: shape for shape in scene.shapes}
    if len(shapes) != len(scene.shapes):
        raise ValueError("Duplicate shape IDs.")
    anchors = {anchor.id: anchor for anchor in scene.anchors}
    if len(anchors) != len(scene.anchors):
        raise ValueError("Duplicate anchor IDs.")
    for shape in scene.shapes:
        if not isinstance(shape, Polygon):
            continue
        points = shape.points
        if len(points) < (3 if shape.kind == "polygon" else 2):
            raise ValueError(f"{shape.id}: too few vertices.")
        if shape.kind == "polyline":
            continue
        edges = list(zip(points, points[1:] + points[:1]))
        area = sum(a[0] * b[1] - b[0] * a[1] for a, b in edges)
        if abs(area) < 1e-6:
            raise ValueError(f"{shape.id}: degenerate polygon.")
        # Proper intersections between nonadjacent edges reject crossed polygons.
        for i, (a, b) in enumerate(edges):
            for j, (c, d) in enumerate(edges[i + 2 :], start=i + 2):
                if i == 0 and j == len(edges) - 1:
                    continue
                ab_c = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
                ab_d = (b[0] - a[0]) * (d[1] - a[1]) - (b[1] - a[1]) * (d[0] - a[0])
                cd_a = (d[0] - c[0]) * (a[1] - c[1]) - (d[1] - c[1]) * (a[0] - c[0])
                cd_b = (d[0] - c[0]) * (b[1] - c[1]) - (d[1] - c[1]) * (b[0] - c[0])
                if ab_c * ab_d < -1e-8 and cd_a * cd_b < -1e-8:
                    raise ValueError(f"{shape.id}: intersecting polygon edges.")
    bound = set()
    for anchor in scene.anchors:
        for vertex in anchor.vertices:
            key = vertex.shape, vertex.index
            if key in bound:
                raise ValueError(f"Vertex bound more than once: {key}")
            bound.add(key)
            shape = shapes.get(vertex.shape)
            if not isinstance(shape, Polygon) or vertex.index >= len(shape.points):
                raise ValueError(f"{anchor.id}: dangling vertex reference {key}")
            if shape.points[vertex.index] != anchor.point:
                raise ValueError(f"{anchor.id}: broken shared position at {key}")


def bind_points(
    scene: Scene, shape: str, start: int, values: list[Vertex]
) -> list[Point]:
    points = []
    for index, value in enumerate(values, start=start):
        if isinstance(value, AnchorRef):
            anchor = next((a for a in scene.anchors if a.id == value.anchor), None)
            if anchor is None:
                raise ValueError(f"Unknown anchor: {value.anchor}")
            anchor.vertices.append(VertexRef(shape=shape, index=index))
            points.append(anchor.point)
        else:
            points.append(value)
    return points


def apply_plan(scene: Scene, plan: EditPlan) -> Scene:
    """Apply atomically to a copy; replaying an identical plan is a no-op."""
    validate_scene(scene)
    if plan.scene and plan.scene != scene.name:
        raise ValueError(f"Plan targets {plan.scene}, not {scene.name}.")
    digest = hashlib.sha256(plan.model_dump_json().encode()).hexdigest()
    previous = next((edit for edit in scene.edits if edit.id == plan.id), None)
    if previous:
        if previous.sha256 != digest:
            raise ValueError(
                "Plan changed after application; replay from the detected scene."
            )
        return scene.model_copy(deep=True)
    result = scene.model_copy(deep=True)
    for operation in plan.operations:
        if isinstance(operation, DefineAnchor):
            if any(a.id == operation.id for a in result.anchors):
                raise ValueError(f"Anchor already exists: {operation.id}")
            result.anchors.append(SharedAnchor(id=operation.id, point=operation.point))
        elif isinstance(operation, MoveAnchor):
            anchor = next((a for a in result.anchors if a.id == operation.id), None)
            if anchor is None:
                raise ValueError(f"Unknown anchor: {operation.id}")
            anchor.point = operation.point
            for vertex in anchor.vertices:
                shape = next(s for s in result.shapes if s.id == vertex.shape)
                if not isinstance(shape, Polygon):
                    raise ValueError(
                        "Only polygon/polyline vertices can share anchors."
                    )
                shape.points[vertex.index] = operation.point
        elif isinstance(operation, ScaleStrokes):
            for shape in result.shapes:
                shape.stroke_width = round(shape.stroke_width * operation.factor, 3)
        else:
            position = next(
                (i for i, s in enumerate(result.shapes) if s.id == operation.shape),
                None,
            )
            if position is None:
                raise ValueError(f"Unknown shape: {operation.shape}")
            target = result.shapes[position]
            if not isinstance(target, Polygon) or target.kind != "polygon":
                raise ValueError("This operation requires a filled polygon.")
            if isinstance(operation, SplitPolygon):
                removed = set(range(len(target.points)))
                replacements = [v for piece in operation.pieces for v in piece.points]
            elif isinstance(operation, ReplacePolygon):
                removed = set(range(len(target.points)))
                replacements = operation.points
            else:
                if operation.start > len(
                    target.points
                ) or operation.start + operation.delete > len(target.points):
                    raise ValueError("Splice is outside the polygon's vertex range.")
                removed = set(
                    range(operation.start, operation.start + operation.delete)
                )
                replacements = operation.points
            retained_anchors = {
                v.anchor for v in replacements if isinstance(v, AnchorRef)
            }
            for anchor in result.anchors:
                if any(
                    v.shape == target.id and v.index in removed for v in anchor.vertices
                ):
                    if anchor.id not in retained_anchors:
                        raise ValueError(
                            f"Edit would detach shared anchor: {anchor.id}"
                        )
                anchor.vertices = [
                    vertex
                    for vertex in anchor.vertices
                    if not (vertex.shape == target.id and vertex.index in removed)
                ]
                if isinstance(operation, SpliceVertices):
                    for vertex in anchor.vertices:
                        if (
                            vertex.shape == target.id
                            and vertex.index >= operation.start + operation.delete
                        ):
                            vertex.index += len(operation.points) - operation.delete
            if isinstance(operation, ReplacePolygon):
                target.points = bind_points(result, target.id, 0, operation.points)
                target.label = operation.label or target.label
            elif isinstance(operation, SpliceVertices):
                target.points[operation.start : operation.start + operation.delete] = (
                    bind_points(result, target.id, operation.start, operation.points)
                )
            else:
                pieces = []
                for piece in operation.pieces:
                    clone = target.model_copy(deep=True)
                    clone.id, clone.label = piece.id, piece.label
                    clone.points = bind_points(result, piece.id, 0, piece.points)
                    pieces.append(clone)
                result.shapes[position : position + 1] = pieces
    result.edits.append(
        AppliedEdit(id=plan.id, sha256=digest, description=plan.description)
    )
    validate_scene(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser(
        "inspect", help="Print shapes and shared anchors for an agent."
    )
    inspect.add_argument("scene", type=Path)
    inspect.add_argument("--shape")
    apply = commands.add_parser("apply", help="Validate and replay a JSON edit plan.")
    apply.add_argument("scene", type=Path)
    apply.add_argument("--plan", type=Path, required=True)
    apply.add_argument("--output", type=Path, required=True)
    commands.add_parser("schema", help="Print the structured edit-plan JSON Schema.")
    args = parser.parse_args()
    if args.command == "schema":
        print(json.dumps(EditPlan.model_json_schema(), indent=2))
        return
    scene = Scene.model_validate_json(args.scene.read_text())
    validate_scene(scene)
    if args.command == "inspect":
        if args.shape:
            shape = next((s for s in scene.shapes if s.id == args.shape), None)
            if shape is None:
                parser.error(f"Unknown shape: {args.shape}")
            inspection = Inspection(
                shape=shape,
                anchors=[
                    anchor
                    for anchor in scene.anchors
                    if any(v.shape == shape.id for v in anchor.vertices)
                ],
            )
            print(inspection.model_dump_json(indent=2))
        else:
            print(scene.model_dump_json(indent=2))
    else:
        plan = EditPlan.model_validate_json(args.plan.read_text())
        edited = apply_plan(scene, plan)
        args.output.write_text(edited.model_dump_json(indent=2) + "\n")
        print(f"Applied {plan.id} → {args.output}")


if __name__ == "__main__":
    main()
