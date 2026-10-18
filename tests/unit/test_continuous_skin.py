"""Focused checks for the continuous, bisector-offset skin construction."""

import importlib
from math import hypot, sqrt
from pathlib import Path

import pytest
from pydantic import TypeAdapter

pytestmark = pytest.mark.unit
STUDY = Path(__file__).parents[2] / "prototypes/photo-vector-study"


@pytest.fixture
def skin(monkeypatch):
    monkeypatch.syspath_prepend(str(STUDY))
    return importlib.import_module("body_skin")


def test_bent_joint_has_two_points_at_the_requested_bisector_offset(skin):
    section = skin.cross_section("elbow", (0, 0), (-100, 0), (0, 100), 18)
    assert section.left == pytest.approx((-18 / sqrt(2), 18 / sqrt(2)))
    assert section.right == pytest.approx((18 / sqrt(2), -18 / sqrt(2)))
    assert hypot(*section.left) == pytest.approx(18)
    assert hypot(*section.right) == pytest.approx(18)


def test_straight_joint_uses_the_perpendicular_cross_section(skin):
    section = skin.cross_section("knee", (0, 0), (-100, 0), (100, 0), 20)
    assert section.left == (0, 20)
    assert section.right == (0, -20)


def test_fully_folded_back_joint_is_rejected(skin):
    with pytest.raises(ValueError, match="no usable direction"):
        skin.cross_section("elbow", (0, 0), (-100, 0), (-100, 0), 18)


def test_all_examples_have_one_body_including_every_joint_section_and_neck(skin):
    poses = TypeAdapter(list[skin.Pose]).validate_json(
        (STUDY / "edits/naked-poses.json").read_text()
    )
    assert len(poses) == 5
    for pose in poses:
        scene, target = skin.build_skin(pose)
        polygons = [s for s in scene.shapes if s.kind == "polygon"]
        assert len(polygons) == 1
        assert polygons[0].id == "body"
        assert {s.part for s in scene.shapes} == {"body", "face"}
        points = polygons[0].points
        assert len(points) == len(target.vertex_sources)
        assert len(set(points)) == len(points)
        for section in target.sections:
            assert section.left in points
            assert section.right in points
            assert hypot(
                section.left[0] - section.right[0], section.left[1] - section.right[1]
            ) == pytest.approx(2 * section.offset)
        assert points == target.body_vertices
        connected = {"pelvis"}
        for _ in target.joints:
            for bone in target.bones:
                if bone.start in connected or bone.end in connected:
                    connected.update((bone.start, bone.end))
        assert connected == set(target.joints)


def test_changing_elbow_offset_changes_only_its_two_skin_vertices(skin):
    pose = TypeAdapter(list[skin.Pose]).validate_json(
        (STUDY / "edits/naked-poses.json").read_text()
    )[1]
    _, before = skin.build_skin(pose)
    wider = pose.model_copy(deep=True)
    wider.overrides["elbow-left"] = 23
    _, after = skin.build_skin(wider)
    assert before.joints == after.joints
    changed = [
        source
        for source, a, b in zip(
            before.vertex_sources, before.body_vertices, after.body_vertices
        )
        if a != b
    ]
    assert set(changed) == {"elbow-left:left", "elbow-left:right"}
