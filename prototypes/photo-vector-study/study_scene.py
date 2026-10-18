"""Typed, application-independent geometry for the photo study and edit tools."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat

INK = "#302d2b"
Point = tuple[FiniteFloat, FiniteFloat]


class ShapeStyle(BaseModel):
    id: str
    source_region: str
    label: str | None = None
    part: str | None = None
    fill: str
    stroke: str = INK
    stroke_width: FiniteFloat = Field(default=6, gt=0)


class Polygon(ShapeStyle):
    kind: Literal["polygon", "polyline"]
    points: list[Point]


class Ellipse(ShapeStyle):
    kind: Literal["ellipse"] = "ellipse"
    center: Point
    radii: tuple[Annotated[float, Field(gt=0)], Annotated[float, Field(gt=0)]]
    rotation: FiniteFloat


class Cubic(BaseModel):
    control1: Point
    control2: Point
    end: Point


class Bezier(ShapeStyle):
    kind: Literal["bezier"] = "bezier"
    start: Point
    segments: list[Cubic]


class Compound(ShapeStyle):
    kind: Literal["compound"] = "compound"
    loops: list[list[Point]] = Field(min_length=1)


class VertexRef(BaseModel):
    shape: str
    index: int = Field(ge=0)


class SharedAnchor(BaseModel):
    id: str
    point: Point
    vertices: list[VertexRef] = Field(default_factory=list)


class AppliedEdit(BaseModel):
    id: str
    sha256: str
    description: str


class PrimitiveFit(BaseModel):
    shape: str
    primitive: str
    source_vertices: int
    fitted_vertices: int
    error_pixels: float
    relative_area_change: float


Shape = Annotated[Polygon | Ellipse | Bezier | Compound, Field(discriminator="kind")]


class Scene(BaseModel):
    model_config = ConfigDict(extra="forbid")
    format: Literal["photo-shape-study"] = "photo-shape-study"
    version: Literal[1] = 1
    name: str
    width: int
    height: int
    method: str = "Voronoi stroke-centre recovery, line fitting and ink skeleton curves"
    interpretation: str = "Detected shapes; user-guided edits are recorded separately."
    shapes: list[Shape]
    anchors: list[SharedAnchor] = Field(default_factory=list)
    edits: list[AppliedEdit] = Field(default_factory=list)
    regularizations: list[PrimitiveFit] = Field(default_factory=list)
