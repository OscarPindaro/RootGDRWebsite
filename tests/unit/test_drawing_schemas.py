import pytest
from pydantic import ValidationError

from backend.drawings.schemas import PathNode, PolygonNode, SceneDocument

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "path", ["M0 0 L", "0 0 M0 0 L1 1", "m0 0 l1 1", "M0 0 Z1 2 L1 1", "M0 0 C1 2"]
)
def test_malformed_or_relative_paths_are_rejected(path):
    with pytest.raises(ValidationError):
        PathNode(id="p", name="Path", d=path)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), 100001])
def test_transform_values_are_finite_and_bounded(value):
    with pytest.raises(ValidationError):
        PolygonNode(
            id="p",
            name="Shape",
            points=[(0, 0), (10, 0), (0, 10)],
            transform=(1, 0, 0, 1, value, 0),
        )


def test_nonzero_area_self_intersecting_polygon_is_rejected():
    with pytest.raises(ValidationError):
        PolygonNode(id="p", name="Shape", points=[(0, 0), (10, 10), (0, 10), (8, 0)])


def test_unknown_formats_and_duplicate_ids_are_rejected():
    with pytest.raises(ValidationError):
        SceneDocument(schema_version=2)
    node = PolygonNode(id="same", name="Shape", points=[(0, 0), (10, 0), (0, 10)])
    with pytest.raises(ValidationError):
        SceneDocument(nodes=[node, node])


def test_colour_cannot_reference_external_content():
    with pytest.raises(ValidationError):
        PolygonNode(
            id="p",
            name="Shape",
            points=[(0, 0), (10, 0), (0, 10)],
            fill="url(https://example.com/image)",
        )
