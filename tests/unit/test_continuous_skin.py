"""Focused checks for the continuous, bisector-offset skin construction."""

import importlib
import json
from math import cos, hypot, radians, sin, sqrt
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


def test_examples_have_one_body_and_a_separate_head_using_only_openpose_joints(skin):
    poses = TypeAdapter(list[skin.Pose]).validate_json(
        (STUDY / "edits/naked-poses.json").read_text()
    )
    assert len(poses) == 5
    for pose in poses:
        scene, target = skin.build_skin(pose)
        polygons = [s for s in scene.shapes if s.kind == "polygon"]
        assert {p.id for p in polygons} == {"body", "head"}
        assert polygons[0].id == "body"
        assert {s.part for s in scene.shapes} == {"body", "head"}
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
        assert not {"head", "jaw", "pelvis", "crotch"} & target.joints.keys()
        assert not {"Neck", "Nose"} & {s.joint for s in target.sections}
        assert set(target.joints) == set(
            skin.OpenPoseFrame.model_validate(pose.openpose.model_dump()).points()
        )
        connected = {"Neck"}
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
    wider.overrides["RElbow"] = 23
    _, after = skin.build_skin(wider)
    assert before.joints == after.joints
    changed = [
        source
        for source, a, b in zip(
            before.vertex_sources, before.body_vertices, after.body_vertices
        )
        if a != b
    ]
    assert set(changed) == {"RElbow:left", "RElbow:right"}


def test_hands_end_in_one_point_and_hips_join_without_a_central_protrusion(skin):
    pose = TypeAdapter(list[skin.Pose]).validate_json(
        (STUDY / "edits/naked-poses.json").read_text()
    )[0]
    _, target = skin.build_skin(pose)
    for wrist, tip in target.hand_tips.items():
        assert target.body_vertices.count(tip) == 1
        index = target.vertex_sources.index(wrist + ":tip")
        section = next(s for s in target.sections if s.joint == wrist)
        assert target.body_vertices[index - 1] == section.right
        assert target.body_vertices[index + 1] == section.left
    bridge = target.vertex_sources.index("LHip:left")
    assert target.vertex_sources[bridge + 1] == "RHip:right"
    assert len(target.body_vertices) == 30


def test_head_follows_nose_rotation_without_changing_the_body(skin):
    pose = TypeAdapter(list[skin.Pose]).validate_json(
        (STUDY / "edits/naked-poses.json").read_text()
    )[0]
    before_scene, before = skin.build_skin(pose)
    changed = pose.model_copy(deep=True)
    neck, nose = before.joints["Neck"], before.joints["Nose"]
    x, y = nose[0] - neck[0], nose[1] - neck[1]
    angle = radians(12)
    changed.openpose.people[0].pose_keypoints_2d[:2] = [
        neck[0] + cos(angle) * x - sin(angle) * y,
        neck[1] + sin(angle) * x + cos(angle) * y,
    ]
    after_scene, after = skin.build_skin(changed)
    assert before.body_vertices == after.body_vertices
    assert (
        after.head_attachment.rotation_degrees - before.head_attachment.rotation_degrees
        == pytest.approx(12)
    )
    assert after.head_attachment.pivot == neck
    assert before_scene.shapes[1].points != after_scene.shapes[1].points
    mark = next(s for s in after_scene.shapes if s.id == "nose-mark")
    assert mark.center == pytest.approx(after.joints["Nose"])


def test_openpose_export_has_eighteen_xy_confidence_triples(skin):
    pose = TypeAdapter(list[skin.Pose]).validate_json(
        (STUDY / "edits/naked-poses.json").read_text()
    )[0]
    frame = skin.OpenPoseFrame.model_validate_json(pose.openpose.model_dump_json())
    flat = frame.people[0].pose_keypoints_2d
    assert len(flat) == 18 * 3
    assert flat[6:9] == [195, 320, 1]  # COCO_18 index 2 is RShoulder.
    assert flat[42:] == [0] * 12  # Unmodeled eye/ear pose landmarks stay missing.


def test_torso_profile_changes_skin_but_not_pose_limbs_or_head(skin):
    pose = TypeAdapter(list[skin.Pose]).validate_json(
        (STUDY / "edits/naked-poses.json").read_text()
    )[1]
    before_scene, before = skin.build_skin(pose)
    # Verify the saved optional-backend artifact without adding Shapely to the app.
    before_data = json.loads(before.model_dump_json())
    after = json.loads((STUDY / "output/torso/broad-chest-target.json").read_text())
    after_scene = skin.Scene.model_validate_json(
        (STUDY / "output/torso/broad-chest.json").read_text()
    )
    for field in ("joints", "bones", "sections", "hand_tips", "head_attachment"):
        assert before_data[field] == after[field]
    assert [s for s in before_scene.shapes if s.part == "head"] == [
        s for s in after_scene.shapes if s.part == "head"
    ]
    assert [s["half_width"] * 2 for s in after["torso_sections"]] == [160, 96]
    sections = skin.sample_rig(pose).sections
    torso = next(c for c in after["components"] if c["id"] == "torso")
    assert tuple(torso["outline"][0]) == sections["RShoulder"].left
    assert tuple(torso["outline"][1]) == sections["LShoulder"].right


def test_equal_chest_and_waist_widths_give_vertical_torso_sides(skin):
    target = json.loads((STUDY / "output/torso/straight-torso-target.json").read_text())
    chest, waist = target["torso_sections"]
    assert chest["left"][0] == waist["left"][0]
    assert chest["right"][0] == waist["right"][0]
    assert chest["center"][1] < waist["center"][1]


def test_waist_control_cannot_be_above_chest(skin):
    with pytest.raises(ValueError, match="below the chest"):
        skin.TorsoProfile(
            chest=skin.TorsoStation(height=0.6, half_width=80),
            waist=skin.TorsoStation(height=0.3, half_width=48),
        )


def test_upper_arm_border_is_rendered_without_shoulder_or_elbow_caps(skin):
    target = json.loads((STUDY / "output/intersections/target.json").read_text())
    scene = skin.Scene.model_validate_json(
        (STUDY / "output/intersections/scene.json").read_text()
    )
    sections = {s["joint"]: s for s in target["sections"]}
    shoulder, elbow = sections["RShoulder"], sections["RElbow"]
    lines = [
        shape
        for shape in scene.shapes
        if shape.source_region == "clipped-occlusion-edge"
    ]
    distance = importlib.import_module("polygon_regularizer").distance
    for fraction in (0.25, 0.5, 0.75):
        p = tuple(
            a * (1 - fraction) + b * fraction
            for a, b in zip(shoulder["right"], elbow["right"])
        )
        assert (
            min(
                distance(p, a, b)
                for line in lines
                for a, b in zip(line.points, line.points[1:])
            )
            < 1e-6
        )
    for section in (shoulder, elbow):
        middle = tuple((a + b) / 2 for a, b in zip(section["left"], section["right"]))
        assert (
            min(
                distance(middle, a, b)
                for line in lines
                for a, b in zip(line.points, line.points[1:])
            )
            > 1
        )


def test_reference_six_is_a_new_intersection_and_twelve_is_retained(skin):
    target = json.loads((STUDY / "output/intersections/target.json").read_text())
    distance = importlib.import_module("polygon_regularizer").distance
    six, twelve = target["reference_markers"]["6"], target["reference_markers"]["12"]
    for component in target["components"]:
        if component["id"] in {"torso", "arm-R"}:
            points = component["outline"]
            assert six not in points
            assert (
                min(
                    distance(six, a, b) for a, b in zip(points, points[1:] + points[:1])
                )
                < 1e-6
            )
    assert twelve in target["body_vertices"]
