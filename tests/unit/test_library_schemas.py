"""The library contract: a fragment is native artwork, not a picture.

These are pure: they pin what a stored fragment may contain, so a library can
never hold something the drawing editor cannot insert back.
"""

import uuid

import pytest
from pydantic import ValidationError

from backend.libraries.schemas import (
    LibraryCreate,
    LibraryScope,
    SceneFragment,
    fragment_node_count,
)
from backend.drawings.schemas import GroupNode, PolygonNode


def _triangle(node_id: str = "t1") -> PolygonNode:
    return PolygonNode(
        id=node_id, name="Becco", points=[(0, 0), (10, 0), (5, 10)], fill="#d97a26"
    )


def test_a_fragment_keeps_native_geometry_and_identities():
    fragment = SceneFragment(
        nodes=[_triangle(), GroupNode(id="g1", name="Gruppo", nodes=[_triangle("t2")])]
    )

    assert fragment.schema_version == 5
    assert fragment.nodes[0].constraint is None
    assert fragment.nodes[0].point_ids
    assert fragment_node_count(fragment.nodes) == 3, "the group counts too"


def test_a_fragment_refuses_what_it_cannot_hold():
    with pytest.raises(ValidationError):
        SceneFragment(nodes=[])
    with pytest.raises(ValidationError):
        SceneFragment(
            nodes=[_triangle(), _triangle()],
        )
    with pytest.raises(ValidationError):
        SceneFragment(
            nodes=[
                GroupNode(id="g", name="G", nodes=[_triangle("same")]),
                _triangle("same"),
            ]
        )


def test_a_fragment_round_trips_through_json():
    fragment = SceneFragment(nodes=[_triangle()])
    again = SceneFragment.model_validate(fragment.model_dump(mode="json"))

    assert again == fragment


def test_a_world_library_needs_a_world_and_a_global_one_does_not():
    world = uuid.uuid4()
    assert LibraryCreate(name="Mondi", scope=LibraryScope.WORLD, world_id=world)
    assert LibraryCreate(name="Comuni", scope=LibraryScope.GLOBAL)
    with pytest.raises(ValidationError):
        LibraryCreate(name="Senza mondo", scope=LibraryScope.WORLD)
    with pytest.raises(ValidationError):
        LibraryCreate(
            name="Globale con mondo", scope=LibraryScope.GLOBAL, world_id=world
        )
    with pytest.raises(ValidationError):
        LibraryCreate(name="X", scope="universe")
