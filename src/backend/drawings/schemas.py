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
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, model_validator

from ..concurrency import VersionedResponse, VersionedUpdate
from ..schemas import AppBaseModel, TimestampMixin, UUIDField

SCENE_FORMAT_VERSION = 1

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
Matrix = tuple[float, float, float, float, float, float]

# Domain data, not a transport envelope: an unknown field is a client bug or a
# future format, and neither should be stored silently.
DOMAIN = ConfigDict(extra="forbid")


class Artboard(AppBaseModel):
    """The drawing surface the scene is composed on."""

    model_config = AppBaseModel.model_config | DOMAIN

    width: Annotated[float, Field(gt=0, le=MAX_COORDINATE)] = 640.0
    height: Annotated[float, Field(gt=0, le=MAX_COORDINATE)] = 480.0
    background: Colour = "#fffdf6"


class NodeBase(AppBaseModel):
    model_config = AppBaseModel.model_config | DOMAIN

    id: NodeId
    name: Annotated[str, Field(min_length=1, max_length=120)]
    transform: Matrix = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    opacity: Opacity = 1.0
    visible: bool = True

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


class PolygonNode(ShapeNode):
    kind: Literal["polygon"] = "polygon"
    points: Annotated[list[Point], Field(min_length=3, max_length=MAX_POLYGON_POINTS)]
    # Per outgoing edge: whether the outline is drawn from this point to the
    # next. Empty means every edge is visible.
    edge_visible: list[bool] | None = None

    @model_validator(mode="after")
    def _polygon_is_valid(self) -> PolygonNode:
        if self.edge_visible is not None and len(self.edge_visible) != len(self.points):
            raise ValueError("edge_visible must have one entry per point")
        if _area(self.points) < MIN_POLYGON_AREA:
            raise ValueError("polygon has no area")
        return self


class EllipseNode(ShapeNode):
    kind: Literal["ellipse"] = "ellipse"
    cx: Coordinate
    cy: Coordinate
    rx: Annotated[float, Field(gt=0, le=MAX_COORDINATE)]
    ry: Annotated[float, Field(gt=0, le=MAX_COORDINATE)]


class PathNode(ShapeNode):
    """An open line or curve, the tool for detail strokes."""

    kind: Literal["path"] = "path"
    d: Annotated[str, Field(min_length=1, max_length=8_000, pattern=_PATH.pattern)]

    @model_validator(mode="after")
    def _path_is_supported(self) -> PathNode:
        commands = parse_path(self.d)
        if len(commands) > MAX_PATH_COMMANDS:
            raise ValueError("path has too many commands")
        if commands[0][0] != "M":
            raise ValueError("path must start with a move command")
        if not any(name in {"L", "C"} for name, _ in commands):
            raise ValueError("path must draw at least one segment")
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

    @model_validator(mode="after")
    def _tree_is_valid(self) -> SceneDocument:
        ids: set[str] = set()
        total = _walk(self.nodes, ids, depth=0)
        if total > MAX_NODES:
            raise ValueError("drawing has too many nodes")
        return self


class DrawingCreate(AppBaseModel):
    title: Annotated[str, Field(min_length=1, max_length=255)]
    scene: SceneDocument | None = None


class DrawingUpdate(VersionedUpdate):
    """An explicit save: the whole document plus the version it was read at.

    The expected version is required here, unlike the content documents: a
    drawing is written as one value, so a missing precondition would silently
    overwrite another session's work.
    """

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


def _walk(nodes: list[Node], ids: set[str], depth: int) -> int:
    if depth > MAX_DEPTH:
        raise ValueError("drawing is nested too deeply")
    total = 0
    for node in nodes:
        if node.id in ids:
            raise ValueError(f"duplicate node id: {node.id}")
        ids.add(node.id)
        total += 1
        if isinstance(node, GroupNode):
            total += _walk(node.nodes, ids, depth + 1)
    return total


def _area(points: list[Point]) -> float:
    """The unsigned area of a polygon, from the shoelace sum."""
    total = 0.0
    for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1], strict=True):
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


_PATH_COMMAND = re.compile(r"([MLCZ])([^MLCZ]*)")


def parse_path(d: str) -> list[tuple[str, list[float]]]:
    """Split an absolute path into commands with their numeric arguments.

    Raises on an unsupported command, a bad argument count or a non-finite
    number, so the stored path is always something the renderer can draw.
    """
    commands: list[tuple[str, list[float]]] = []
    for name, raw in _PATH_COMMAND.findall(d.upper()):
        numbers: list[float] = []
        for token in raw.replace(",", " ").split():
            try:
                numbers.append(float(token))
            except ValueError:
                raise ValueError("path has a non-numeric argument") from None
        expected = {"M": 2, "L": 2, "C": 6, "Z": 0}[name]
        if expected and len(numbers) % expected != 0:
            raise ValueError(f"path command {name} has the wrong argument count")
        if any(abs(value) > MAX_COORDINATE for value in numbers):
            raise ValueError("path has a coordinate out of range")
        commands.append((name, numbers))
    if not commands:
        raise ValueError("path has no commands")
    return commands
