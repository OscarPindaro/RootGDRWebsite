/* Pure tests for the drawing editor's algorithms (node --test).

   The browser tests cover the interaction; these cover the maths and the
   document operations, where a wrong answer is invisible on screen until the
   artwork is already broken. */

import assert from "node:assert/strict";
import { test } from "node:test";

import {
  apply,
  bounds,
  centerOf,
  distanceToSegment,
  invert,
  multiply,
  pointInPolygon,
  polygonArea,
  rotateAbout,
  scaleAbout,
  translation,
} from "../../src/frontend/js/drawings/geometry.js";
import {
  History,
  addNode,
  createPolygon,
  createRect,
  cutNode,
  depthOf,
  duplicateNode,
  edgesOf,
  findNode,
  groupNodes,
  isSimplePolygon,
  newId,
  nodeAt,
  nodeBounds,
  patchNode,
  pathPoints,
  removeNode,
  reorderNode,
  splitPolygonAt,
  ungroupNode,
  validPolygon,
  walk,
  worldPoints,
} from "../../src/frontend/js/drawings/scene.js";
import { visibleRuns } from "../../src/frontend/js/drawings/render.js";

const IDENTITY = [1, 0, 0, 1, 0, 0];

function sceneWith(nodes) {
  return { schemaVersion: 1, artboard: { width: 640, height: 480, background: "#fffdf6" }, nodes };
}

function triangle(id = "a") {
  return {
    ...createPolygon("Triangolo", [[0, 0], [100, 0], [50, 100]]),
    id,
  };
}

test("a matrix composes and inverts back to the original point", () => {
  const matrix = multiply(translation(30, -10), multiply(rotateAbout([0, 0], Math.PI / 3), scaleAbout([0, 0], 2, 3)));
  const point = [12.5, -7.25];
  const roundTrip = apply(invert(matrix), apply(matrix, point));
  assert.ok(Math.abs(roundTrip[0] - point[0]) < 1e-9);
  assert.ok(Math.abs(roundTrip[1] - point[1]) < 1e-9);
});

test("a singular matrix has no inverse", () => {
  assert.equal(invert([0, 0, 0, 0, 5, 5]), null);
});

test("polygon area, containment and bounds agree", () => {
  const square = [[0, 0], [10, 0], [10, 10], [0, 10]];
  assert.equal(polygonArea(square), 100);
  assert.equal(pointInPolygon([5, 5], square), true);
  assert.equal(pointInPolygon([15, 5], square), false);
  assert.deepEqual(bounds(square), { minX: 0, minY: 0, maxX: 10, maxY: 10 });
  assert.deepEqual(centerOf(square), [5, 5]);
});

test("distance to a segment clamps to its endpoints", () => {
  assert.equal(distanceToSegment([5, 3], [0, 0], [10, 0]), 3);
  assert.equal(distanceToSegment([-4, 0], [0, 0], [10, 0]), 4);
});

test("ids are unique", () => {
  const ids = new Set(Array.from({ length: 200 }, () => newId("x")));
  assert.equal(ids.size, 200);
});

test("walk visits every node, groups included", () => {
  const scene = sceneWith([
    triangle("a"),
    { kind: "group", id: "g", name: "Gruppo", transform: IDENTITY, opacity: 1, visible: true, nodes: [triangle("b"), triangle("c")] },
  ]);
  const ids = [];
  walk(scene.nodes, (node) => ids.push(node.id));
  assert.deepEqual(ids, ["a", "g", "b", "c"]);
});

test("adding, removing and reordering keep the tree consistent", () => {
  const scene = sceneWith([triangle("a"), triangle("b")]);
  const withNode = addNode(scene, triangle("c"));
  assert.deepEqual(withNode.nodes.map((n) => n.id), ["a", "b", "c"]);
  assert.deepEqual(scene.nodes.map((n) => n.id), ["a", "b"], "the input is untouched");

  const removed = removeNode(withNode, "b");
  assert.deepEqual(removed.nodes.map((n) => n.id), ["a", "c"]);

  const reordered = reorderNode(withNode, "a", 1);
  assert.deepEqual(reordered.nodes.map((n) => n.id), ["b", "a", "c"]);
  assert.deepEqual(reorderNode(withNode, "c", 5).nodes.map((n) => n.id), ["a", "b", "c"]);
});

test("duplicating gives fresh ids, a name and an offset", () => {
  const scene = sceneWith([triangle("a")]);
  const result = duplicateNode(scene, "a");
  assert.equal(result.scene.nodes.length, 2);
  const copy = result.scene.nodes[1];
  assert.notEqual(copy.id, "a");
  assert.match(copy.name, /copia/);
  assert.deepEqual(copy.transform, [1, 0, 0, 1, 16, 16]);
});

test("worldPoints applies the node transform", () => {
  const node = { ...triangle("a"), transform: translation(10, 20) };
  assert.deepEqual(worldPoints(node), [[10, 20], [110, 20], [60, 120]]);
});

test("nodeBounds follows the kind", () => {
  assert.deepEqual(nodeBounds(triangle("a")), { minX: 0, minY: 0, maxX: 100, maxY: 100 });
  const ellipse = { kind: "ellipse", cx: 10, cy: 10, rx: 5, ry: 2, transform: IDENTITY };
  assert.deepEqual(nodeBounds(ellipse), { minX: 5, minY: 8, maxX: 15, maxY: 12 });
});

test("a path flattens to points, curves included", () => {
  const points = pathPoints("M0 0 L10 0 C10 5 20 5 20 0 Z");
  assert.deepEqual(points[0], [0, 0]);
  assert.deepEqual(points[1], [10, 0]);
  assert.deepEqual(points[points.length - 1], [0, 0]);
  assert.ok(points.length > 3);
});

test("hit testing finds the topmost shape and ignores a hidden one", () => {
  const scene = sceneWith([triangle("a")]);
  assert.equal(nodeAt(scene, [50, 20]).id, "a");
  assert.equal(nodeAt(scene, [500, 500]), null);

  const hidden = patchNode(scene, "a", { visible: false });
  assert.equal(nodeAt(hidden, [50, 20]), null);
});

test("hit testing respects the node transform", () => {
  const scene = sceneWith([{ ...triangle("a"), transform: translation(200, 100) }]);
  assert.equal(nodeAt(scene, [250, 120]).id, "a");
  assert.equal(nodeAt(scene, [50, 20]), null);
});

test("a polygon with no area is invalid", () => {
  assert.equal(validPolygon([[0, 0], [1, 1], [2, 2]]), false);
  assert.equal(validPolygon([[0, 0], [10, 0], [10, 10]]), true);
});

test("edgesOf drops the hidden edges", () => {
  const node = { ...triangle("a"), edgeVisible: [true, false, true] };
  const edges = edgesOf(node);
  assert.deepEqual(edges, [[[0, 0], [100, 0]], [[50, 100], [0, 0]]]);
});

test("visibleRuns joins the wrap-around edge when it is visible", () => {
  const all = { ...triangle("a"), edgeVisible: [true, true, true] };
  assert.equal(visibleRuns(all).length, 1);
  assert.equal(visibleRuns(all)[0].length, 4, "closed outline");

  const broken = { ...triangle("a"), edgeVisible: [false, true, true] };
  const runs = visibleRuns(broken);
  assert.equal(runs.length, 1);
  assert.deepEqual(runs[0], [[100, 0], [50, 100], [0, 0]]);

  const twoGaps = { ...triangle("a"), edgeVisible: [true, false, false] };
  assert.deepEqual(visibleRuns(twoGaps), [[[0, 0], [100, 0]]]);
});

test("history undoes, redoes and branches", () => {
  const history = new History(sceneWith([triangle("a")]));
  const two = addNode(history.present, triangle("b"));
  history.commit(two);
  assert.equal(history.present.nodes.length, 2);
  assert.equal(history.canUndo, true);

  const one = history.undo();
  assert.equal(one.nodes.length, 1);
  assert.equal(history.canRedo, true);

  const redo = history.redo();
  assert.equal(redo.nodes.length, 2);

  history.undo();
  const branched = addNode(history.present, triangle("c"));
  history.commit(branched);
  assert.equal(history.canRedo, false, "a new change clears the redo stack");
  assert.deepEqual(history.present.nodes.map((n) => n.id), ["a", "c"]);
});

test("history ignores a commit that changes nothing", () => {
  const history = new History(sceneWith([triangle("a")]));
  history.commit(sceneWith([triangle("a")]));
  assert.equal(history.canUndo, false);
});

test("history is bounded", () => {
  const history = new History(sceneWith([]), 3);
  for (let index = 0; index < 6; index += 1) {
    history.commit(addNode(history.present, triangle(`n${index}`)));
  }
  assert.equal(history.past.length, 3);
});

test("a rectangle is a four-point polygon", () => {
  const rect = createRect("Rettangolo", [30, 20], [10, 60]);
  assert.deepEqual(rect.points, [[10, 20], [30, 20], [30, 60], [10, 60]]);
  assert.equal(rect.kind, "polygon");
});

test("findNode reports the containing list", () => {
  const scene = sceneWith([triangle("a"), triangle("b")]);
  const found = findNode(scene, "b");
  assert.equal(found.index, 1);
  assert.equal(found.siblings.length, 2);
});

/* ---------- straight cut ---------- */

const SQUARE = [[0, 0], [100, 0], [100, 100], [0, 100]];
// An L: the region x>40 and y>40 is outside it.
const L_SHAPE = [[0, 0], [100, 0], [100, 40], [40, 40], [40, 100], [0, 100]];

test("a square splits along its diagonal into two triangles", () => {
  const split = splitPolygonAt(SQUARE, 0, 2);
  assert.deepEqual(split.aIndices, [0, 1, 2]);
  assert.deepEqual(split.bIndices, [2, 3, 0]);
  assert.equal(polygonArea(split.aPoints), 5000);
  assert.equal(polygonArea(split.bPoints), 5000);
});

test("a cut needs two non-adjacent vertices", () => {
  assert.equal(splitPolygonAt(SQUARE, 0, 0), null);
  assert.equal(splitPolygonAt(SQUARE, 0, 1), null, "adjacent");
  assert.equal(splitPolygonAt(SQUARE, 1, 0), null, "adjacent the other way");
  assert.equal(splitPolygonAt([[0, 0], [10, 0], [5, 10]], 0, 1), null, "a triangle");
});

test("a chord that leaves a concave polygon is refused", () => {
  assert.equal(splitPolygonAt(L_SHAPE, 1, 5), null);
  // A chord that stays inside the same shape is accepted.
  assert.ok(splitPolygonAt(L_SHAPE, 1, 3));
});

test("a concave polygon with a self-intersecting piece is refused", () => {
  // A bowtie: the pieces of any chord cross themselves.
  const bowtie = [[0, 0], [100, 100], [100, 0], [0, 100]];
  assert.equal(isSimplePolygon(bowtie), false);
  assert.equal(splitPolygonAt(bowtie, 0, 2), null);
});

test("cutNode keeps the original id, hides the cut edges and adds a sibling", () => {
  const scene = sceneWith([{ ...createPolygon("Becco", SQUARE), id: "beak" }]);
  const result = cutNode(scene, "beak", 0, 2);

  assert.ok(result);
  assert.equal(result.scene.nodes.length, 2);
  const [original, piece] = result.scene.nodes;
  assert.equal(original.id, "beak");
  assert.equal(piece.id, result.id);
  assert.match(piece.name, /tagliata/);
  // The shared cut edge is hidden on both pieces; the perimeter stays drawn.
  assert.equal(original.edgeVisible[original.edgeVisible.length - 1], false);
  assert.equal(piece.edgeVisible[piece.edgeVisible.length - 1], false);
  assert.equal(original.edgeVisible[0], true);
  // The source document is untouched.
  assert.equal(scene.nodes.length, 1);
});

test("cutNode refuses a polygon it cannot split", () => {
  const scene = sceneWith([{ ...createPolygon("Becco", SQUARE), id: "beak" }]);
  assert.equal(cutNode(scene, "beak", 0, 1), null);
  assert.equal(cutNode(scene, "missing", 0, 2), null);
});

/* ---------- grouping ---------- */

test("grouping siblings keeps every child where it was", () => {
  const scene = sceneWith([
    { ...triangle("a"), transform: translation(10, 10) },
    { ...triangle("b"), transform: translation(200, 40) },
    triangle("c"),
  ]);
  const result = groupNodes(scene, ["a", "b"]);

  assert.ok(result);
  assert.equal(result.scene.nodes.length, 2);
  const group = result.scene.nodes[0];
  assert.equal(group.kind, "group");
  assert.deepEqual(group.transform, [1, 0, 0, 1, 0, 0], "an identity group moves nothing");
  assert.deepEqual(group.nodes.map((node) => node.id), ["a", "b"]);
  assert.deepEqual(worldPoints(group.nodes[0]), worldPoints(scene.nodes[0]));
  assert.deepEqual(result.scene.nodes[1].id, "c");
});

test("grouping refuses a mixed level, a single node or a group too deep", () => {
  const scene = sceneWith([
    triangle("a"),
    {
      kind: "group",
      id: "g",
      name: "Gruppo",
      transform: IDENTITY,
      opacity: 1,
      visible: true,
      nodes: [triangle("b")],
    },
  ]);
  assert.equal(groupNodes(scene, ["a"]), null, "one node");
  assert.equal(groupNodes(scene, ["a", "b"]), null, "not siblings");
  assert.equal(groupNodes(scene, ["a", "missing"]), null);

  // Two siblings at the deepest allowed level: grouping them would nest once
  // too far for the document format.
  let nodes = [triangle("deep")];
  for (let level = 0; level < 8; level += 1) {
    nodes = [
      {
        kind: "group",
        id: `g${level}`,
        name: "Gruppo",
        transform: IDENTITY,
        opacity: 1,
        visible: true,
        nodes,
      },
    ];
  }
  let innermost = nodes;
  while (innermost[0].kind === "group") innermost = innermost[0].nodes;
  innermost.push(triangle("sibling"));

  assert.equal(depthOf(nodes, "deep"), 9);
  assert.equal(groupNodes(sceneWith(nodes), ["deep", "sibling"]), null);
});

test("ungrouping composes the transforms so nothing moves", () => {
  const scene = sceneWith([
    {
      kind: "group",
      id: "g",
      name: "Gruppo",
      transform: translation(50, 20),
      opacity: 1,
      visible: true,
      nodes: [{ ...triangle("a"), transform: translation(5, 5) }],
    },
  ]);
  const result = ungroupNode(scene, "g");

  assert.ok(result);
  assert.deepEqual(result.ids, ["a"]);
  assert.equal(result.scene.nodes.length, 1);
  assert.equal(result.scene.nodes[0].id, "a");
  // The child's world position is the same as it was inside the group.
  assert.deepEqual(result.scene.nodes[0].transform, [1, 0, 0, 1, 55, 25]);
  assert.deepEqual(worldPoints(result.scene.nodes[0]), [[55, 25], [155, 25], [105, 125]]);
});

test("ungrouping a non-group is refused", () => {
  const scene = sceneWith([triangle("a")]);
  assert.equal(ungroupNode(scene, "a"), null);
  assert.equal(ungroupNode(scene, "missing"), null);
});

test("depthOf reports the nesting level", () => {
  const scene = sceneWith([
    {
      kind: "group",
      id: "g",
      name: "Gruppo",
      transform: IDENTITY,
      opacity: 1,
      visible: true,
      nodes: [triangle("a")],
    },
  ]);
  assert.equal(depthOf(scene.nodes, "g"), 1);
  assert.equal(depthOf(scene.nodes, "a"), 2);
  assert.equal(depthOf(scene.nodes, "missing"), 0);
});
