import pytest
from pydantic import ValidationError

from backend.drawings.schemas import (
    EllipseNode,
    GroupNode,
    PathNode,
    PolygonNode,
    SceneDocument,
)

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
        SceneDocument(schema_version=99)
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


def test_legacy_native_migration_is_deterministic_and_does_not_infer_locks():
    legacy = {
        "schemaVersion": 1,
        "nodes": [
            {
                "kind": "polygon",
                "id": "old",
                "name": "Rettangolo",
                "points": [[0, 0], [100, 0], [80, 70]],
                "transform": [2, 0, 0, 3, 10, 20],
            }
        ],
    }
    first = SceneDocument.model_validate(legacy)
    second = SceneDocument.model_validate(legacy)
    assert first.schema_version == 4
    assert first == second
    assert first.nodes[0].constraint is None
    assert first.nodes[0].point_ids == ["v0", "v1", "v2"]
    assert first.nodes[0].points == [(0, 0), (100, 0), (80, 70)]
    assert legacy["schemaVersion"] == 1
    assert SceneDocument.model_validate(first.model_dump(by_alias=True)) == first


@pytest.mark.parametrize(
    "nodes",
    [None, "bad", [{"kind": "group", "id": "g", "name": "Group", "nodes": None}]],
)
def test_malformed_legacy_trees_are_validation_errors(nodes):
    with pytest.raises(ValidationError):
        SceneDocument.model_validate({"schemaVersion": 1, "nodes": nodes})


def test_stable_element_ids_reject_duplicates_and_wrong_counts():
    base = {"id": "p", "name": "Shape", "points": [(0, 0), (10, 0), (0, 10)]}
    for ids in (["a", "a", "c"], ["a", "b"], []):
        with pytest.raises(ValidationError):
            PolygonNode(**base, point_ids=ids)


@pytest.mark.parametrize(
    "constraint,points",
    [
        ("rectangle", [(0, 0), (10, 0), (8, 10), (0, 10)]),
        ("square", [(0, 0), (10, 0), (10, 20), (0, 20)]),
        ("triangle_equilateral", [(0, 0), (10, 0), (5, 10)]),
        ("triangle_right_right", [(0, 10), (10, 10), (5, 0)]),
        ("triangle_isosceles", [(0, 10), (10, 10), (2, 0)]),
    ],
)
def test_native_constraints_reject_incompatible_geometry(constraint, points):
    with pytest.raises(ValidationError):
        PolygonNode(
            id="p", name="Shape", points=points, constraint={"kind": constraint}
        )


def test_locked_square_rejects_nonuniform_parent_transform():
    scene = {
        "schemaVersion": 2,
        "nodes": [
            {
                "kind": "group",
                "id": "g",
                "name": "Group",
                "transform": [2, 0, 0, 3, 0, 0],
                "nodes": [
                    {
                        "kind": "polygon",
                        "id": "p",
                        "name": "Square",
                        "points": [[0, 0], [10, 0], [10, 10], [0, 10]],
                        "constraint": {"kind": "square"},
                    }
                ],
            }
        ],
    }
    with pytest.raises(ValidationError):
        SceneDocument.model_validate(scene)
    scene["nodes"][0]["nodes"][0]["constraint"] = None
    assert SceneDocument.model_validate(scene).nodes[0].nodes[0].constraint is None


@pytest.mark.parametrize("transform", [(2, 0, 0, 3, 0, 0), (1, 0, 1, 1, 0, 0)])
def test_locked_circles_reject_incompatible_own_and_parent_transforms(transform):
    circle = EllipseNode(
        id="circle",
        name="Circle",
        cx=0,
        cy=0,
        rx=10,
        ry=10,
        constraint={"kind": "circle"},
    )
    with pytest.raises(ValidationError):
        SceneDocument(nodes=[circle.model_copy(update={"transform": transform})])
    with pytest.raises(ValidationError):
        SceneDocument(
            nodes=[GroupNode(id="g", name="Group", transform=transform, nodes=[circle])]
        )
    circle.constraint = None
    assert SceneDocument(
        nodes=[GroupNode(id="g", name="Group", transform=transform, nodes=[circle])]
    )


def test_reflected_uniform_circle_transform_and_legacy_named_ellipse_remain_valid():
    circle = EllipseNode(
        id="c",
        name="Circle",
        cx=0,
        cy=0,
        rx=10,
        ry=10,
        constraint={"kind": "circle"},
        transform=(-2, 0, 0, 2, 0, 0),
    )
    assert SceneDocument(nodes=[circle]).nodes[0].constraint.kind == "circle"
    legacy = SceneDocument.model_validate(
        {
            "schemaVersion": 1,
            "nodes": [
                {
                    "kind": "ellipse",
                    "id": "old",
                    "name": "Cerchio",
                    "cx": 10,
                    "cy": 20,
                    "rx": 30,
                    "ry": 15,
                }
            ],
        }
    )
    assert legacy.nodes[0].constraint is None
    assert legacy.nodes[0].rx == 30 and legacy.nodes[0].ry == 15


def test_transform_pivots_round_trip_and_version_two_keeps_geometry_locks():
    old = {
        "schemaVersion": 2,
        "nodes": [
            {
                "kind": "polygon",
                "id": "p",
                "name": "Square",
                "points": [[0, 0], [100, 0], [100, 100], [0, 100]],
                "pointIds": ["a", "b", "c", "d"],
                "constraint": {"kind": "square"},
            }
        ],
    }
    migrated = SceneDocument.model_validate(old)
    assert migrated.schema_version == 4
    assert migrated.nodes[0].point_ids == ["a", "b", "c", "d"]
    assert migrated.nodes[0].constraint.kind == "square"
    assert migrated.nodes[0].pivot is None
    migrated.nodes[0].pivot = (20, 30)
    assert SceneDocument.model_validate(migrated.model_dump(by_alias=True)).nodes[
        0
    ].pivot == (20, 30)
    with pytest.raises(ValidationError):
        migrated.nodes[0].pivot = (float("nan"), 0)


def test_curve_and_anchor_identities_round_trip():
    scene = SceneDocument.model_validate(
        {
            "nodes": [
                {
                    "kind": "path",
                    "id": "p",
                    "name": "Curve",
                    "d": "M0 0 C10 20 30 20 40 0",
                    "anchors": [
                        {
                            "id": "grip",
                            "name": "Grip",
                            "position": [10, 10],
                            "angle": 0.5,
                        }
                    ],
                }
            ]
        }
    )
    assert scene.nodes[0].point_ids == ["h0", "h1", "h2", "h3"]
    assert SceneDocument.model_validate(scene.model_dump(by_alias=True)) == scene
