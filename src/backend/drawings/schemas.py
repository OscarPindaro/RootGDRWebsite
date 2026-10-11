"""The native drawing document and the transport schemas around it.

A drawing is an ordered tree of groups and shapes plus the artboard it is drawn
on. The document is the editable original; an SVG or PNG export is derived from
it and never replaces it.

Everything here validates before it is stored: the format version, the shape
tags, the numbers, the matrices, the colours and the geometry itself. Unknown
fields and unknown versions are rejected rather than silently dropped, so a
document written by a future version cannot lose data by being read here.
"""

from __future__ import annotations

import re
from copy import deepcopy
from math import isclose
from typing import Annotated, Any, Literal

from pydantic import ConfigDict, Field, model_validator

from ..concurrency import VersionedResponse, VersionedUpdate
from ..schemas import AppBaseModel, TimestampMixin, UUIDField

SCENE_FORMAT_VERSION = 2

# Bounds: a drawing is a bounded illustration, not an unlimited scene. The
# numbers are generous for the intended artwork and keep a request cheap to
# validate and to render.
MAX_NODES = 2_000
MAX_POLYGON_POINTS = 256
MAX_PATH_COMMANDS = 512
MAX_DEPTH = 8
MAX_COORDINATE = 100_000.0
MIN_POLYGON_AREA = 1e-6

_COLOUR = re.compile(r"^#[0-9a-fA-F]{6}$")
_NODE_ID = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
# Absolute commands only in this version: the client emits M/L/C/Z with explicit
# coordinates, which keeps bounds checking and later editing unambiguous.
_PATH = re.compile(r"^[MLCZmlcz0-9 ,.\-]+$")

Colour = Annotated[str, Field(pattern=_COLOUR.pattern)]
NodeId = Annotated[str, Field(pattern=_NODE_ID.pattern)]
Coordinate = Annotated[float, Field(ge=-MAX_COORDINATE, le=MAX_COORDINATE)]
Opacity = Annotated[float, Field(ge=0.0, le=1.0)]
StrokeWidth = Annotated[float, Field(ge=0.0, le=100.0)]
Point = tuple[Coordinate, Coordinate]
Matrix = tuple[Coordinate, Coordinate, Coordinate, Coordinate, Coordinate, Coordinate]

# Domain data, not a transport envelope: an unknown field is a client bug or a
# future format, and neither should be stored silently.
DOMAIN = ConfigDict(extra="forbid", allow_inf_nan=False)


class Artboard(AppBaseModel):
    """The drawing surface the scene is composed on."""

    model_config = AppBaseModel.model_config | DOMAIN

    width: Annotated[float, Field(gt=0, le=MAX_COORDINATE)] = 640.0
    height: Annotated[float, Field(gt=0, le=MAX_COORDINATE)] = 480.0
    background: Colour = "#fffdf6"


class GeometryConstraint(AppBaseModel):
    model_config = AppBaseModel.model_config | DOMAIN

    kind: Literal[
        "triangle_isosceles",
        "triangle_equilateral",
        "triangle_right_right",
        "triangle_right_left",
        "rectangle",
        "square",
        "regular_polygon",
        "circle",
    ]


class NativeAnchor(AppBaseModel):
    model_config = AppBaseModel.model_config | DOMAIN

    id: NodeId
    name: Annotated[str, Field(min_length=1, max_length=120)]
    position: Point
    angle: Annotated[float, Field(ge=-360, le=360)] = 0


class NodeBase(AppBaseModel):
    model_config = AppBaseModel.model_config | DOMAIN

    id: NodeId
    name: Annotated[str, Field(min_length=1, max_length=120)]
    transform: Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    opacity: Opacity = 1.0
    visible: bool = True
    anchors: Annotated[list[NativeAnchor], Field(max_length=256)] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def _transform_is_invertible(self) -> NodeBase:
        a, b, c, d, _e, _f = self.transform
        if abs(a * d - b * c) < 1e-9:
            raise ValueError("transform must be invertible")
        return self


class ShapeNode(NodeBase):
    """A fill and an outline. ``stroke`` may be None to hide the whole outline."""

    fill: Colour | None = None
    stroke: Colour | None = "#17150f"
    stroke_width: StrokeWidth = 4.0
    constraint: GeometryConstraint | None = None


class PolygonNode(ShapeNode):
    kind: Literal["polygon"] = "polygon"
    points: Annotated[list[Point], Field(min_length=3, max_length=MAX_POLYGON_POINTS)]
    # Per outgoing edge: whether the outline is drawn from this point to the
    # next. Empty means every edge is visible.
    edge_visible: list[bool] | None = None
    point_ids: Annotated[list[NodeId], Field(max_length=MAX_POLYGON_POINTS)] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def _polygon_is_valid(self) -> PolygonNode:
        if self.edge_visible is not None and len(self.edge_visible) != len(self.points):
            raise ValueError("edge_visible must have one entry per point")
        if _area(self.points) < MIN_POLYGON_AREA:
            raise ValueError("polygon has no area")
        if not simple_polygon(self.points):
            raise ValueError("polygon must be simple")
        if "point_ids" not in self.model_fields_set and not self.point_ids:
            self.point_ids.extend(f"v{i}" for i in range(len(self.points)))
        if len(self.point_ids) != len(self.points) or len(set(self.point_ids)) != len(
            self.point_ids
        ):
            raise ValueError("point_ids must be unique and match polygon points")
        if self.constraint and not locked_polygon(self.points, self.constraint.kind):
            raise ValueError("geometry does not satisfy the primitive constraint")
        return self


class EllipseNode(ShapeNode):
    kind: Literal["ellipse"] = "ellipse"
    cx: Coordinate
    cy: Coordinate
    rx: Annotated[float, Field(gt=0, le=MAX_COORDINATE)]
    ry: Annotated[float, Field(gt=0, le=MAX_COORDINATE)]

    @model_validator(mode="after")
    def _ellipse_constraint(self) -> EllipseNode:
        if self.constraint and (
            self.constraint.kind != "circle"
            or not isclose(self.rx, self.ry, rel_tol=1e-6)
        ):
            raise ValueError("circle constraint requires equal radii")
        return self


class PathNode(ShapeNode):
    """An open line or curve, the tool for detail strokes."""

    kind: Literal["path"] = "path"
    d: Annotated[str, Field(min_length=1, max_length=8_000, pattern=_PATH.pattern)]
    point_ids: Annotated[list[NodeId], Field(max_length=MAX_PATH_COMMANDS * 6)] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def _path_is_supported(self) -> PathNode:
        commands = parse_path(self.d)
        if len(commands) > MAX_PATH_COMMANDS:
            raise ValueError("path has too many commands")
        if commands[0][0] != "M":
            raise ValueError("path must start with a move command")
        if not any(name in {"L", "C"} for name, _ in commands):
            raise ValueError("path must draw at least one segment")
        count = sum(len(numbers) // 2 for _, numbers in commands)
        if "point_ids" not in self.model_fields_set and not self.point_ids:
            self.point_ids.extend(f"h{i}" for i in range(count))
        if len(self.point_ids) != count or len(set(self.point_ids)) != count:
            raise ValueError("point_ids must be unique and match path handles")
        if self.constraint:
            raise ValueError("paths cannot have primitive constraints")
        return self


class GroupNode(NodeBase):
    kind: Literal["group"] = "group"
    nodes: list[Node] = Field(default_factory=list)


Node = PolygonNode | EllipseNode | PathNode | GroupNode

GroupNode.model_rebuild()


class SceneDocument(AppBaseModel):
    """The complete editable drawing, as stored."""

    model_config = AppBaseModel.model_config | DOMAIN

    schema_version: Literal[SCENE_FORMAT_VERSION] = SCENE_FORMAT_VERSION
    artboard: Artboard = Field(default_factory=Artboard)
    nodes: Annotated[list[Node], Field(max_length=MAX_NODES)] = Field(
        default_factory=list
    )

    @model_validator(mode="before")
    @classmethod
    def _migrate_v1(cls, value: Any) -> Any:
        if (
            not isinstance(value, dict)
            or value.get(
                "schemaVersion", value.get("schema_version", SCENE_FORMAT_VERSION)
            )
            != 1
        ):
            return value
        if not isinstance(value.get("nodes", []), list):
            raise ValueError("drawing nodes must be a list")
        migrated = deepcopy(value)
        nodes = list(migrated.get("nodes", []))
        total = 0
        while nodes:
            node = nodes.pop()
            total += 1
            if total > MAX_NODES:
                raise ValueError("drawing has too many nodes")
            if not isinstance(node, dict):
                continue
            if any(
                key in node
                for key in ("constraint", "anchors", "pointIds", "point_ids")
            ):
                raise ValueError("version 1 cannot contain version 2 geometry metadata")
            if node.get("kind") == "group":
                if not isinstance(node.get("nodes", []), list):
                    raise ValueError("group nodes must be a list")
                nodes.extend(node.get("nodes", []))
        key = "schemaVersion" if "schemaVersion" in migrated else "schema_version"
        migrated[key] = SCENE_FORMAT_VERSION
        return migrated

    @model_validator(mode="after")
    def _tree_is_valid(self) -> SceneDocument:
        ids: set[str] = set()
        total = _walk(self.nodes, ids, depth=0)
        if total > MAX_NODES:
            raise ValueError("drawing has too many nodes")
        if len(self.model_dump_json().encode()) > 1_048_576:
            raise ValueError("drawing exceeds the native document size limit")
        return self


class DrawingCreate(AppBaseModel):
    model_config = AppBaseModel.model_config | DOMAIN

    title: Annotated[str, Field(min_length=1, max_length=255)]
    scene: SceneDocument | None = None


class DrawingUpdate(VersionedUpdate):
    """An explicit save: the whole document plus the version it was read at.

    The expected version is required here, unlike the content documents: a
    drawing is written as one value, so a missing precondition would silently
    overwrite another session's work.
    """

    model_config = AppBaseModel.model_config | DOMAIN

    expected_version: Annotated[int, Field(ge=1)]
    title: Annotated[str | None, Field(default=None, min_length=1, max_length=255)]
    scene: SceneDocument | None = None


class DrawingSummary(AppBaseModel, TimestampMixin, VersionedResponse):
    id: Annotated[UUIDField, Field(description="Drawing ID")]
    title: Annotated[str, Field(description="Name")]
    node_count: Annotated[int, Field(default=0, description="Top-level objects")]


class DrawingResponse(DrawingSummary):
    scene: Annotated[SceneDocument, Field(description="The editable document")]


def default_scene() -> SceneDocument:
    """The blank document a new drawing starts from."""
    return SceneDocument()


def count_nodes(scene: SceneDocument) -> int:
    """Top-level objects, the number the list shows."""
    return len(scene.nodes)


def _walk(
    nodes: list[Node], ids: set[str], depth: int, parent: Matrix = (1, 0, 0, 1, 0, 0)
) -> int:
    if depth > MAX_DEPTH:
        raise ValueError("drawing is nested too deeply")
    total = 0
    for node in nodes:
        if node.id in ids:
            raise ValueError(f"duplicate node id: {node.id}")
        ids.add(node.id)
        total += 1
        a, b, c, d, e, f = parent
        na, nb, nc, nd, ne, nf = node.transform
        world = (
            a * na + c * nb,
            b * na + d * nb,
            a * nc + c * nd,
            b * nc + d * nd,
            a * ne + c * nf + e,
            b * ne + d * nf + f,
        )
        anchor_ids = [anchor.id for anchor in node.anchors]
        element_ids = anchor_ids + (
            node.point_ids if isinstance(node, (PolygonNode, PathNode)) else []
        )
        if len(set(element_ids)) != len(element_ids):
            raise ValueError("element identities must be unique within a node")
        if isinstance(node, PolygonNode) and node.constraint:
            wa, wb, wc, wd, we, wf = world
            points = [
                (wa * x + wc * y + we, wb * x + wd * y + wf) for x, y in node.points
            ]
            if not locked_polygon(points, node.constraint.kind):
                raise ValueError("world transform violates a geometry constraint")
        if isinstance(node, EllipseNode) and node.constraint:
            wa, wb, wc, wd, _, _ = world
            if not isclose(
                wa * wa + wb * wb, wc * wc + wd * wd, rel_tol=1e-6
            ) or not isclose(wa * wc + wb * wd, 0, abs_tol=1e-6 * (wa * wa + wb * wb)):
                raise ValueError(
                    "world transform would turn a locked circle into an ellipse"
                )
        if isinstance(node, GroupNode):
            total += _walk(node.nodes, ids, depth + 1, world)
    return total


def locked_polygon(points: list[Point], kind: str) -> bool:
    if kind == "circle":
        return False
    size = len(points)
    edges = [
        (points[(i + 1) % size][0] - x, points[(i + 1) % size][1] - y)
        for i, (x, y) in enumerate(points)
    ]
    lengths = [x * x + y * y for x, y in edges]
    equal = lambda x, y: isclose(x, y, rel_tol=1e-6, abs_tol=1e-8)
    perpendicular = lambda u, v: (
        abs(u[0] * v[0] + u[1] * v[1])
        <= 1e-6 * (sum(n * n for n in u) * sum(n * n for n in v)) ** 0.5
    )
    if kind.startswith("triangle_"):
        if size != 3:
            return False
        if kind == "triangle_isosceles":
            return equal(lengths[1], lengths[2])
        if kind == "triangle_equilateral":
            return all(equal(lengths[0], length) for length in lengths[1:])
        corner = 1 if kind == "triangle_right_right" else 0
        return perpendicular(edges[corner], edges[(corner - 1) % size])
    if kind in {"rectangle", "square"}:
        rectangle = size == 4 and all(
            perpendicular(edges[i], edges[(i + 1) % size]) for i in range(size)
        )
        return rectangle and (kind == "rectangle" or equal(lengths[0], lengths[1]))
    cx, cy = sum(x for x, _ in points) / size, sum(y for _, y in points) / size
    radii = [(x - cx) ** 2 + (y - cy) ** 2 for x, y in points]
    return all(equal(lengths[0], length) for length in lengths[1:]) and all(
        equal(radii[0], radius) for radius in radii[1:]
    )


def _area(points: list[Point]) -> float:
    """The unsigned area of a polygon, from the shoelace sum."""
    total = 0.0
    for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1], strict=True):
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def simple_polygon(points: list[Point]) -> bool:
    def cross(a: Point, b: Point, c: Point) -> float:
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def on(a: Point, b: Point, p: Point) -> bool:
        return (
            abs(cross(a, b, p)) < 1e-9
            and min(a[0], b[0]) <= p[0] <= max(a[0], b[0])
            and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])
        )

    size = len(points)
    if len(set(points)) != size:
        return False
    for i, a in enumerate(points):
        b = points[(i + 1) % size]
        for j in range(i + 1, size):
            if j == i + 1 or (i == 0 and j == size - 1):
                continue
            c, d = points[j], points[(j + 1) % size]
            if (
                cross(a, b, c) * cross(a, b, d) < 0
                and cross(c, d, a) * cross(c, d, b) < 0
            ):
                return False
            if on(a, b, c) or on(a, b, d) or on(c, d, a) or on(c, d, b):
                return False
    return True


_PATH_COMMAND = re.compile(r"([MLCZ])([^MLCZ]*)")


def parse_path(d: str) -> list[tuple[str, list[float]]]:
    """Split an absolute path into commands with their numeric arguments.

    Raises on an unsupported command, a bad argument count or a non-finite
    number, so the stored path is always something the renderer can draw.
    """
    if not re.fullmatch(r"M[0-9 ,.\-MLCZ]+", d) or re.search(r"[a-z]", d):
        raise ValueError("path must contain absolute supported commands")
    commands: list[tuple[str, list[float]]] = []
    for name, raw in _PATH_COMMAND.findall(d):
        numbers: list[float] = []
        for token in raw.replace(",", " ").split():
            try:
                numbers.append(float(token))
            except ValueError:
                raise ValueError("path has a non-numeric argument") from None
        expected = {"M": 2, "L": 2, "C": 6, "Z": 0}[name]
        if (expected and (not numbers or len(numbers) % expected)) or (
            not expected and numbers
        ):
            raise ValueError(f"path command {name} has the wrong argument count")
        if any(abs(value) > MAX_COORDINATE for value in numbers):
            raise ValueError("path has a coordinate out of range")
        commands.append((name, numbers))
    if not commands:
        raise ValueError("path has no commands")
    return commands
