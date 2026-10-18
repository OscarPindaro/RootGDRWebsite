"""Contracts for shared-vertex edits on the committed drawing examples."""

import importlib
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit
STUDY = Path(__file__).parents[2] / "prototypes" / "photo-vector-study"


@pytest.fixture
def tools(monkeypatch):
    monkeypatch.syspath_prepend(str(STUDY))
    return importlib.import_module("shape_edits")


def load_scene(tools, name, *, detected=False):
    suffix = "-detected" if detected else ""
    return tools.Scene.model_validate_json(
        (STUDY / "output/shapes" / f"{name}{suffix}.json").read_text()
    )


def test_collar_recipe_is_repeatable_and_keeps_neighbours_attached(tools):
    original = load_scene(tools, "altus", detected=True)
    before = original.model_dump()
    plan = tools.EditPlan.model_validate_json((STUDY / "edits/altus.json").read_text())
    corrected = tools.apply_plan(original, plan)
    collar = next(s for s in corrected.shapes if s.id == "region-160-0")
    assert len(collar.points) == 3
    shapes = {s.id: s for s in corrected.shapes}
    left, right, tip = collar.points
    assert [shapes["region-164-0"].points[0], shapes["region-164-0"].points[-1]] == [
        left,
        tip,
    ]
    assert shapes["region-156-0"].points[:2] == [right, tip]
    assert shapes["region-025-0"].points[2:4] == [left, right]
    assert [len(a.vertices) for a in corrected.anchors] == [3, 3, 4]
    tools.validate_scene(corrected)
    assert original.model_dump() == before
    assert tools.apply_plan(corrected, plan) == corrected


def test_moving_shared_corner_moves_all_four_attached_pieces(tools):
    original = load_scene(tools, "altus")
    before = original.model_dump()
    tip = next(a for a in original.anchors if a.id == "collar-tip")
    destination = (tip.point[0] + 2, tip.point[1] + 3)
    edited = tools.apply_plan(
        original,
        tools.EditPlan(
            id="move-collar-tip",
            description="Move the collar point while retaining both cape panels and chest.",
            operations=[
                tools.MoveAnchor(op="move_anchor", id=tip.id, point=destination)
            ],
        ),
    )
    for reference in tip.vertices:
        shape = next(s for s in edited.shapes if s.id == reference.shape)
        assert shape.points[reference.index] == destination
    assert original.model_dump() == before


def test_invalid_later_operation_does_not_partially_apply(tools):
    original = load_scene(tools, "altus")
    before = original.model_dump()
    plan = tools.EditPlan(
        id="invalid-transaction",
        description="An invalid target must roll back the preceding style change.",
        operations=[
            tools.ScaleStrokes(op="scale_strokes", factor=2),
            tools.ReplacePolygon(
                op="replace_polygon",
                shape="missing",
                points=[(0, 0), (10, 0), (5, 10)],
            ),
        ],
    )
    with pytest.raises(ValueError, match="Unknown shape"):
        tools.apply_plan(original, plan)
    assert original.model_dump() == before


def test_polygon_replacement_cannot_silently_drop_shared_corners(tools):
    original = load_scene(tools, "altus")
    plan = tools.EditPlan(
        id="detach-by-accident",
        description="Reject unbound replacements.",
        operations=[
            tools.ReplacePolygon(
                op="replace_polygon",
                shape="region-160-0",
                points=[(150, 154), (213, 150), (181.11, 199.59)],
            )
        ],
    )
    with pytest.raises(ValueError, match="detach shared anchor"):
        tools.apply_plan(original, plan)


def test_revised_recipe_requires_replay_and_strokes_do_not_accumulate(tools):
    original = load_scene(tools, "wolf", detected=True)
    plan = tools.EditPlan.model_validate_json(
        (STUDY / "edits/outline.json").read_text()
    )
    edited = tools.apply_plan(original, plan)
    assert edited.shapes[0].stroke_width == pytest.approx(
        original.shapes[0].stroke_width * 1.35
    )
    assert tools.apply_plan(edited, plan) == edited
    changed = plan.model_copy(update={"description": "Changed recipe"})
    with pytest.raises(ValueError, match="replay from the detected scene"):
        tools.apply_plan(edited, changed)


def test_luciano_wings_have_requested_geometry_and_shared_split_edge(tools):
    scene = load_scene(tools, "luciano")
    shapes = {s.id: s for s in scene.shapes}
    assert len(shapes["region-098-0"].points) == 3
    wing = shapes["region-126-0"]
    underwing = shapes["luciano-right-underwing"]
    assert len(wing.points) == 4
    assert wing.points[2] == underwing.points[-1]
    assert wing.points[3] == underwing.points[0]
    tools.validate_scene(scene)
