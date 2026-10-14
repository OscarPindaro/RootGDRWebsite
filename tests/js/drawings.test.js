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
  resizeFrame,
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
  return { schemaVersion: 6, artboard: { width: 640, height: 480, background: "#fffdf6" }, nodes };
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
  history.commit(history.present);
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

test("reparenting keeps world transforms and rejects cycles", async () => {
  const {reparentNode, nodeFrame} = await import("../../src/frontend/js/drawings/scene.js");
  const scene = sceneWith([triangle("a"), {kind:"group", id:"g", name:"Group", visible:true, opacity:1, transform:translation(100, 20), nodes:[]}]);
  const before = nodeFrame(scene, "a").world;
  const moved = reparentNode(scene, "a", "g").scene;
  assert.deepEqual(nodeFrame(moved, "a").world, before);
  assert.equal(moved.nodes[0].nodes[0].id, "a");
  assert.equal(reparentNode(moved, "g", "g"), null);
  const nested = reparentNode(sceneWith([{kind:"group", id:"outer", name:"Outer", visible:true, opacity:1, transform:IDENTITY, nodes:[moved.nodes[0]]}]), "outer", "g");
  assert.equal(nested, null);
});

test("each cubic control is attached to its own endpoint", async () => {
  const { pathHandles } = await import("../../src/frontend/js/drawings/scene.js");
  const handles = pathHandles("M0 0 C10 20 30 20 40 0");
  assert.deepEqual(handles[1].anchor, [0, 0]);
  assert.deepEqual(handles[2].anchor, [40, 0]);
});

test("curve controls retain commands when edited", async () => {
  const { pathHandles, movePathPoint } = await import("../../src/frontend/js/drawings/scene.js");
  const d = "M0 0 C10 20 30 20 40 0";
  assert.equal(pathHandles(d).length, 4);
  assert.equal(pathHandles(d).filter(h => h.control).length, 2);
  assert.equal(movePathPoint(d, 1, 0, [10, 30]), "M0 0 C10 30 30 20 40 0");
});

test("nested frames, hit tests and world translation agree", async () => {
  const { nodeFrame, transformInWorld } = await import("../../src/frontend/js/drawings/scene.js");
  const scene = sceneWith([{ kind: "group", id: "g", name: "Group", transform: [2, 0, 0, 2, 100, 20], opacity: 1, visible: true, nodes: [triangle("a")] }]);
  assert.deepEqual(nodeFrame(scene, "a").world, [2, 0, 0, 2, 100, 20]);
  assert.equal(nodeAt(scene, [200, 60]).id, "a");
  const moved = transformInWorld(scene, "a", translation(20, 0));
  assert.deepEqual(moved.nodes[0].nodes[0].transform, [1, 0, 0, 1, 10, 0]);
  assert.equal(nodeAt(patchNode(scene, "g", {visible: false}), [200, 60]), null);
});

test("nonconsecutive grouping preserves stacking by refusing", () => {
  assert.equal(groupNodes(sceneWith([triangle("a"), triangle("b"), triangle("c")]), ["a", "c"]), null);
});

test("all original cut edges keep their visibility", () => {
  const node = {...triangle("a"), points: SQUARE, edgeVisible: null};
  const result = cutNode(sceneWith([node]), "a", 0, 2);
  assert.deepEqual(result.scene.nodes[1].edgeVisible, [true, true, false]);
  assert.equal(cutNode(sceneWith([node]), "a", 0, 20), null);
});

test("native migration preserves legacy geometry and assigns stable scoped identities", async () => {
  const {migrateScene} = await import("../../src/frontend/js/drawings/scene.js");
  const legacy = {schemaVersion:1, artboard:{width:640,height:480,background:"#fffdf6"}, nodes:[{...triangle("a"), name:"Triangolo"}]};
  delete legacy.nodes[0].pointIds;
  delete legacy.nodes[0].constraint;
  const migrated = migrateScene(legacy);
  assert.equal(migrated.schemaVersion, 6);
  assert.equal(legacy.schemaVersion, 1);
  assert.deepEqual(migrated.nodes[0].points, legacy.nodes[0].points);
  assert.deepEqual(migrated.nodes[0].pointIds, ["v0","v1","v2"]);
  assert.equal(migrated.nodes[0].constraint, null);
  assert.deepEqual(migrateScene(migrated), migrated);
});

test("constraints reject incompatible edits and parent transforms without changing the source", async () => {
  const {constraintsValid, transformInWorld} = await import("../../src/frontend/js/drawings/scene.js");
  const square = {...createRect("Square",[0,0],[100,100]),id:"p",constraint:{kind:"square"}};
  const scene = sceneWith([{kind:"group",id:"g",name:"Group",transform:IDENTITY,opacity:1,visible:true,anchors:[],nodes:[square]}]);
  assert.equal(constraintsValid(scene),true);
  assert.deepEqual(transformInWorld(scene,"g",scaleAbout([0,0],2,3)),scene);
  assert.deepEqual(patchNode(scene,"p",{points:[[0,0],[100,0],[80,100],[0,100]]}),scene);
  assert.equal(cutNode(scene,"p",0,2),null);
  const unlocked = patchNode(scene,"p",{constraint:null});
  assert.notDeepEqual(transformInWorld(unlocked,"g",scaleAbout([0,0],2,3)),unlocked);
  const copy = duplicateNode(scene,"p").scene.nodes[0].nodes[1];
  assert.deepEqual(copy.pointIds,square.pointIds);
  assert.deepEqual(copy.constraint,square.constraint);
});

test("all polygon presets retain their invariant through constrained editing", async () => {
  const {createPreset, editPresetVertex, constraintsValid} = await import("../../src/frontend/js/drawings/scene.js");
  for (const kind of ["triangle_isosceles","triangle_equilateral","triangle_right_right","triangle_right_left","rectangle","square","regular_polygon"]) {
    const node = createPreset(kind,[100,100],[260,220],6);
    assert.ok(node,kind);
    assert.equal(constraintsValid(sceneWith([node])),true,kind);
    const identities = [...node.pointIds];
    const next = patchNode(sceneWith([node]), node.id, {points:editPresetVertex(node,0,[80,140])});
    assert.equal(constraintsValid(next),true,kind);
    assert.deepEqual(next.nodes[0].pointIds,identities,kind);
  }
  assert.equal(createPreset("regular_polygon",[0,0],[100,100],2),null);
  assert.equal(createPreset("rectangle",[0,0],[0,100]),null);
});

test("circle presets and atomic selection transforms cannot introduce oval distortion", async () => {
  const {createPreset, constraintsValid, transformNodesInWorld, nodeFrame} = await import("../../src/frontend/js/drawings/scene.js");
  const circle = createPreset("circle",[0,0],[200,100]);
  assert.equal(circle.rx,50);
  assert.equal(circle.ry,50);
  const ellipse = createPreset("ellipse",[0,0],[200,100]);
  assert.equal(ellipse.constraint,null);
  assert.equal(ellipse.rx,100);
  assert.equal(ellipse.ry,50);
  const scene = sceneWith([circle,ellipse]);
  const entries = scene.nodes.map(node => ({id:node.id,transform:nodeFrame(scene,node.id).world}));
  assert.deepEqual(transformNodesInWorld(scene,entries,scaleAbout([0,0],2,3)),scene);
  assert.equal(constraintsValid(transformNodesInWorld(scene,entries,scaleAbout([0,0],-2,2))),true);
});

test("oriented resize keeps every opposite anchor fixed under nested and reflected matrices", () => {
  const local = [[0,0],[100,0],[100,80],[0,80]];
  for (const matrix of [[1,0,0,1,20,30],[-2,0.3,0.2,3,60,70],multiply(translation(100,20),rotateAbout([0,0],Math.PI / 3))]) {
    const corners = local.map(point => apply(matrix,point));
    for (let corner = 0; corner < 4; corner += 1) {
      const wanted = apply(matrix,[local[corner][0] === 0 ? -40 : 140, local[corner][1] === 0 ? -16 : 96]);
      const frame = resizeFrame(corners,corner,wanted);
      const delta = multiply(frame.basis,multiply([frame.sx,0,0,frame.sy,0,0],frame.inverse));
      const fixed = corners[(corner + 2) % 4];
      const unchanged = apply(delta,fixed), resized = apply(delta,corners[corner]);
      assert.ok(Math.hypot(unchanged[0]-fixed[0],unchanged[1]-fixed[1]) < 1e-8);
      assert.ok(Math.hypot(resized[0]-wanted[0],resized[1]-wanted[1]) < 1e-8);
    }
  }
  assert.equal(resizeFrame(local,0,[NaN,0]),null);
  assert.equal(resizeFrame([[0,0],[0,0],[0,0],[0,0]],0,[10,10]),null);
  assert.ok(resizeFrame([[0,0],[100,0],[100,0],[0,0]],1,[150,0]));
});

test("visibility diagnosis preserves empty/hidden/unpainted objects without phantom canvas hits", async () => {
  const {visibilityIssues, createEllipse} = await import("../../src/frontend/js/drawings/scene.js");
  const invisible = {...triangle("p"),fill:null,stroke:null};
  const scene = sceneWith([{kind:"group",id:"g",name:"Hidden",visible:false,opacity:1,transform:IDENTITY,nodes:[invisible]},{kind:"group",id:"empty",name:"Empty",visible:true,opacity:1,transform:IDENTITY,nodes:[]}]);
  assert.deepEqual(visibilityIssues(scene,null),["no-selection"]);
  assert.deepEqual(visibilityIssues(scene,"p"),["hidden-parent","no-paint"]);
  assert.deepEqual(visibilityIssues(scene,"empty"),["empty-group"]);
  assert.equal(nodeAt(sceneWith([invisible]),[50,0]),null);
  const ellipse = createEllipse("Ellipse",[100,100],40,20);
  ellipse.fill = ellipse.stroke = null;
  assert.equal(nodeAt(sceneWith([ellipse]),[100,100]),null);
  assert.equal(nodeAt(sceneWith([{...triangle("p"),opacity:0}]),[50,20]),null);
  assert.equal(scene.nodes.length,2);
});

test("compact commands parse triangle refinements without evaluating unknown input", async () => {
  const {parseCompact} = await import("../../src/frontend/js/drawings/canvas-palette.js");
  assert.equal(parseCompact("triangle").kind,"triangle_isosceles");
  assert.equal(parseCompact("rect","triangle_isosceles").kind,"triangle_right_right");
  assert.equal(parseCompact("rect left","triangle_isosceles").kind,"triangle_right_left");
  assert.equal(parseCompact("right","triangle_right_left").kind,"triangle_right_right");
  assert.equal(parseCompact("equilateral","triangle_isosceles").kind,"triangle_equilateral");
  assert.equal(parseCompact("", "triangle_right_left").kind,"triangle_right_left");
  assert.equal(parseCompact("rect invalid","triangle_isosceles"),null);
  assert.equal(parseCompact("window.alert(1)"),null);
});

test("numeric geometry and local pivots preserve nested locks and reject incompatible dimensions", async () => {
  const {createPreset, geometryInfo, editGeometry, nodeFrame} = await import("../../src/frontend/js/drawings/scene.js");
  const node = {...createPreset("square",[100,100],[200,200]),id:"p",pivot:null};
  const scene = sceneWith([{kind:"group",id:"g",name:"Group",transform:[2,0,0,2,20,30],opacity:1,visible:true,pivot:null,anchors:[],nodes:[node]}]);
  const before = geometryInfo(scene,["p"]);
  assert.equal(before.width,200);
  const edited = editGeometry(scene,["p"],{width:300, x:250, y:300, pivotX:120, pivotY:130});
  assert.ok(edited);
  assert.equal(geometryInfo(edited,["p"]).width,300);
  assert.deepEqual(findNode(edited,"p").node.pivot,[120,130]);
  assert.equal(findNode(edited,"p").node.constraint.kind,"square");
  assert.deepEqual(findNode(edited,"p").node.pointIds,node.pointIds);
  assert.equal(editGeometry(scene,["p"],{width:200,height:100}),null);
  assert.equal(editGeometry(scene,["p"],{width:NaN}),null);
  assert.deepEqual(nodeFrame(scene,"p").world,[2,0,0,2,20,30]);
});

test("alignment and spacing distribution only translate complete selections", async () => {
  const {alignNodes, geometryInfo} = await import("../../src/frontend/js/drawings/scene.js");
  const a = {...createRect("A",[0,0],[40,40]),id:"a"};
  const b = {...createRect("B",[100,50],[160,90]),id:"b"};
  const c = {...createRect("C",[300,100],[380,140]),id:"c"};
  const scene=sceneWith([a,b,c]);
  const aligned=alignNodes(scene,["a","b","c"],"top");
  assert.deepEqual(["a","b","c"].map(id => geometryInfo(aligned,[id]).y),[0,0,0]);
  const spread=alignNodes(scene,["a","b","c"],"distribute-x");
  const boxes=["a","b","c"].map(id => geometryInfo(spread,[id]));
  assert.equal(boxes[1].x-(boxes[0].x+boxes[0].width),boxes[2].x-(boxes[1].x+boxes[1].width));
  assert.equal(alignNodes(scene,["a"],"left"),null);
});

test("numeric command parsing is bounded and preserves case-sensitive parent identities", async () => {
  const {parseNumericCommand} = await import("../../src/frontend/js/drawings/canvas-palette.js");
  assert.deepEqual(parseNumericCommand("move 20 30").parameters,{dx:20,dy:30});
  assert.deepEqual(parseNumericCommand("pivot 50 60").parameters,{pivotX:50,pivotY:60});
  assert.deepEqual(parseNumericCommand("parent HeadGroup").parameters,{parent:"HeadGroup"});
  assert.deepEqual(parseNumericCommand("parent root").parameters,{parent:null});
  assert.equal(parseNumericCommand("move NaN 20"),null);
  assert.equal(parseNumericCommand("align unknown"),null);
  assert.equal(parseNumericCommand("eval 10 20"),null);
});

test("edit locks cover descendants independently from visibility and primitive constraints", async () => {
  const {editLocked, editableSelection, transformNodesInWorld} = await import("../../src/frontend/js/drawings/scene.js");
  const node = {...createRect("Locked",[100,100],[200,200]),id:"p",editLocked:false};
  const scene=sceneWith([{kind:"group",id:"g",name:"Group",transform:[1,0,0,1,0,0],opacity:1,visible:true,editLocked:true,nodes:[node]}]);
  assert.equal(editLocked(scene,"p"),true);
  assert.equal(editableSelection(scene,["p"]),false);
  assert.equal(nodeAt(scene,[150,150]),null);
  assert.equal(transformNodesInWorld(scene,[{id:"p",transform:[1,0,0,1,0,0]}],[1,0,0,1,10,20]),scene);
  scene.nodes[0].editLocked=false;
  node.editLocked=true;
  assert.equal(editableSelection(scene,["g"]),false);
});

test("the compact second stage takes a size, a vertex count and a variant", async () => {
  const {parseCompact} = await import("../../src/frontend/js/drawings/canvas-palette.js");
  assert.deepEqual(parseCompact("130", "triangle_isosceles"),{kind:"triangle_isosceles",size:130,sides:null});
  assert.deepEqual(parseCompact("isoscele 130", "triangle_isosceles"),{kind:"triangle_isosceles",size:130,sides:null});
  assert.deepEqual(parseCompact("equilatero 80", "triangle_isosceles"),{kind:"triangle_equilateral",size:80,sides:null});
  assert.deepEqual(parseCompact("rect left 60", "triangle_isosceles"),{kind:"triangle_right_left",size:60,sides:null});
  assert.deepEqual(parseCompact("6", "regular_polygon"),{kind:"regular_polygon",size:null,sides:6});
  assert.deepEqual(parseCompact("", "regular_polygon"),{kind:"regular_polygon",size:null,sides:null});
  assert.equal(parseCompact("2", "regular_polygon"),null);
  assert.equal(parseCompact("99", "regular_polygon"),null);
  assert.equal(parseCompact("0", "triangle_isosceles"),null);
  assert.equal(parseCompact("-5", "triangle_isosceles"),null);
  assert.equal(parseCompact("molti", "triangle_isosceles"),null);
  assert.equal(parseCompact("130", "triangle_isosceles").size,130);
  // The first stage still resolves a shape name and rejects anything else.
  assert.equal(parseCompact("triangle").kind,"triangle_isosceles");
  assert.equal(parseCompact("not-a-shape"),null);
});

test("an accepted variant can be restated by any name its family answers to", async () => {
  const {parseCompact} = await import("../../src/frontend/js/drawings/canvas-palette.js");
  // Regression: after accepting a right triangle, `triangolo` used to be
  // refused because only the selected variant's aliases were consulted.
  for (const accepted of ["triangle_right_right","triangle_right_left","triangle_equilateral","triangle_isosceles"]) {
    assert.deepEqual(parseCompact("triangolo", accepted),{kind:accepted,size:null,sides:null});
    assert.deepEqual(parseCompact("triangle", accepted),{kind:accepted,size:null,sides:null});
    assert.deepEqual(parseCompact("130 triangolo", accepted),{kind:accepted,size:130,sides:null});
  }
  // A variant word still selects the variant, from any starting variant.
  assert.equal(parseCompact("isoscele","triangle_right_left").kind,"triangle_isosceles");
  assert.equal(parseCompact("equilatero","triangle_isosceles").kind,"triangle_equilateral");
  assert.equal(parseCompact("sinistra","triangle_right_right").kind,"triangle_right_left");
  // A word that belongs to no part of the family is still refused.
  assert.equal(parseCompact("quadrato","triangle_isosceles"),null);
  assert.equal(parseCompact("rettangolo","regular_polygon"),null);
});

test("a linked instance keeps its source, records overrides and refreshes around them", async () => {
  const {createInstance, noteOverride, owningInstance, refreshInstance, createRect, detachInstance, findNode, walk} = await import("../../src/frontend/js/drawings/scene.js");
  const source={libraryId:"lib-1", assetId:"asset-1"};
  const blade=createRect("Lama",[0,0],[100,10]);
  const hilt=createRect("Elsa",[0,10],[20,30]);
  const scene=sceneWith([createInstance("Spada",source,3,[blade,hilt])]);
  const instance=scene.nodes[0];
  assert.equal(instance.kind,"instance");
  assert.equal(instance.revision,3);
  assert.deepEqual(instance.overrides,[]);
  assert.equal(instance.nodes.length,2);
  assert.equal(owningInstance(scene,blade.id),instance.id);
  assert.equal(owningInstance(scene,instance.id),null);

  // A local colour change is recorded, not just applied.
  const recoloured=noteOverride(scene,blade.id,"fill");
  findNode(recoloured,blade.id).node.fill="#d1402a";
  assert.deepEqual(findNode(recoloured,instance.id).node.overrides,["fill"]);
  assert.deepEqual(noteOverride(recoloured,blade.id,"fill").nodes[0].overrides,["fill"],"recorded once");

  // The library moves on: a longer blade under the same identity, a new node,
  // a new colour.
  const longer={...createRect("Lama",[0,0],[180,10]), id:blade.id, pointIds:blade.pointIds};
  longer.fill="#000000";
  const refreshed=refreshInstance(recoloured,instance.id,[longer,hilt,createRect("Pomello",[0,30],[10,40])],4);
  const merged=findNode(refreshed,instance.id).node;
  assert.equal(merged.revision,4);
  assert.equal(merged.nodes.length,3,"the new node arrives");
  const mergedBlade=merged.nodes.find(node=>node.id===blade.id);
  assert.deepEqual(mergedBlade.points,[[0,0],[180,0],[180,10],[0,10]],"geometry comes from the library");
  assert.equal(mergedBlade.fill,"#d1402a","the local colour is kept");
  assert.equal(merged.nodes.find(node=>node.id===hilt.id).fill,hilt.fill);

  // A source that no longer holds an overridden node simply brings the new set.
  const without=refreshInstance(recoloured,instance.id,[longer],5);
  assert.equal(findNode(without,instance.id).node.nodes.length,1);
  assert.equal(refreshInstance(scene,instance.id,[],4),null);
  assert.equal(refreshInstance(scene,instance.id,[longer],0),null);
  assert.equal(refreshInstance(scene,blade.id,[longer],4),null,"only an instance refreshes");
});

test("making an instance independent keeps the artwork where it was", async () => {
  const {createInstance, detachInstance, createRect, findNode, walk} = await import("../../src/frontend/js/drawings/scene.js");
  const instance=createInstance("Spada",{libraryId:"l",assetId:"a"},1,[createRect("Lama",[0,0],[100,10]),createRect("Elsa",[0,10],[20,30])]);
  instance.transform=[2,0,0,2,10,20];
  instance.opacity=0.5;
  const scene=sceneWith([instance]);
  const result=detachInstance(scene,instance.id);
  assert.ok(result);
  assert.equal(result.scene.nodes.length,2,"the instance is replaced by its children");
  assert.ok(result.scene.nodes.every(node=>node.kind==="polygon"));
  assert.ok(result.scene.nodes.every(node=>node.transform[0]===2 && node.transform[4]===10),"the placement is composed in");
  assert.ok(result.scene.nodes.every(node=>node.opacity===0.5));
  assert.deepEqual(result.ids,result.scene.nodes.map(node=>node.id));
  assert.ok(!findNode(result.scene,instance.id),"the link is gone");
  const ids=[]; walk(result.scene.nodes,node=>ids.push(node.id));
  assert.equal(new Set(ids).size,ids.length);
  assert.equal(detachInstance(scene,"nope"),null);
  assert.equal(detachInstance(scene,result.scene.nodes[0].id),null,"only an instance detaches");
});

test("a library fragment is inserted as an independent copy with fresh identities", async () => {
  const {withFreshIds, createRect, createPath, createPolygon} = await import("../../src/frontend/js/drawings/scene.js");
  const original=createRect("Becco",[0,0],[100,100]);
  const copy=withFreshIds(original);
  assert.notEqual(copy.id,original.id);
  assert.equal(copy.name,"Becco","the name is kept");
  assert.deepEqual(copy.points,original.points);
  assert.equal(copy.pointIds.length,4);
  assert.equal(new Set(copy.pointIds).size,4);
  assert.ok(copy.pointIds.every(id=>!original.pointIds.includes(id)),"fresh point identities");
  assert.notEqual(copy.transform,undefined);

  // A group is relabelled all the way down.
  const group={kind:"group",id:"g",name:"Corpo",transform:[1,0,0,1,0,0],opacity:1,visible:true,pivot:null,editLocked:false,anchors:[{id:"a1",name:"mano",point:[0,0]}],nodes:[createRect("Braccio",[0,0],[10,10])]};
  const groupCopy=withFreshIds(group);
  assert.notEqual(groupCopy.id,"g");
  assert.notEqual(groupCopy.nodes[0].id,group.nodes[0].id);
  assert.equal(groupCopy.nodes[0].pointIds.every(id=>!group.nodes[0].pointIds.includes(id)),true);
  assert.notEqual(groupCopy.anchors[0].id,"a1");
  assert.equal(groupCopy.anchors[0].name,"mano","an anchor keeps its meaning");
});

test("the artboard is editable and content bounds are the export alternative", async () => {
  const {patchArtboard, contentBounds, createRect, createEllipse} = await import("../../src/frontend/js/drawings/scene.js");
  const scene=sceneWith([{...createRect("Box",[0,0],[100,100]),id:"box"}]);
  const wide=patchArtboard(scene,{width:800,height:600,background:"#ffffff"});
  assert.deepEqual(wide.artboard,{width:800,height:600,background:"#ffffff"});
  assert.deepEqual(scene.artboard,{width:640,height:480,background:"#fffdf6"},"the source is untouched");

  // Content outside the artboard still counts, and hidden nodes do not.
  const outside=sceneWith([
    {...createRect("Box",[0,0],[100,100]),id:"box"},
    {...createEllipse("Far",[900,900],50,50),id:"far"},
  ]);
  assert.deepEqual(contentBounds(outside),{minX:0,minY:0,maxX:950,maxY:950});
  const hidden=sceneWith([{...createRect("Box",[0,0],[100,100]),id:"box",visible:false}]);
  assert.equal(contentBounds(hidden),null,"nothing visible");
  assert.equal(contentBounds(sceneWith([])),null);
  // A node hidden by its parent is not in the rendered result either.
  const nested=sceneWith([{kind:"group",id:"g",name:"Group",transform:[1,0,0,1,0,0],opacity:1,visible:false,nodes:[{...createRect("Box",[0,0],[100,100]),id:"box"}]}]);
  assert.deepEqual(contentBounds(nested),{minX:0,minY:0,maxX:100,maxY:100});
});

test("a line cuts a polygon into two simple pieces and hides the new edges", async () => {
  const {splitPolygonByLine, cutNodesByLine, constraintsValid} = await import("../../src/frontend/js/drawings/scene.js");
  const square=[[0,0],[100,0],[100,100],[0,100]];
  const vertical={point:[50,0],direction:[0,1]};
  const split=splitPolygonByLine(square,vertical);
  assert.ok(split);
  const span = piece => [Math.min(...piece.points.map(p=>p[0])), Math.max(...piece.points.map(p=>p[0]))];
  assert.deepEqual(span(split.a),[0,50],"the two halves are on either side");
  assert.deepEqual(span(split.b),[50,100]);
  assert.equal(split.a.points.length,4);
  assert.equal(split.b.points.length,4);
  assert.ok(Math.abs(polygonArea(split.a.points) - 5000) < 1e-6);
  assert.ok(Math.abs(polygonArea(split.b.points) - 5000) < 1e-6);
  // The edge along the cut starts hidden on both halves.
  assert.equal(split.a.visible.includes(false),true);
  assert.equal(split.b.visible.includes(false),true);
  assert.equal(split.a.visible.filter(value => value === false).length,1);
  // A diagonal cuts the same square into two triangles.
  const diagonal=splitPolygonByLine(square,{point:[0,0],direction:[1,1]});
  assert.ok(diagonal);
  assert.equal(diagonal.a.points.length,3);
  assert.equal(diagonal.b.points.length,3);
  assert.ok(Math.abs(polygonArea(diagonal.a.points) - 5000) < 1e-6);

  const scene=sceneWith([{...createRect("Box",[0,0],[100,100]),id:"box",pointIds:["a","b","c","d"]}]);
  const cut=cutNodesByLine(scene,["box"],vertical);
  assert.equal(cut.nodes.length,2);
  assert.equal(cut.nodes[0].id,"box","the original keeps its id");
  assert.equal(cut.nodes[0].points.length,4);
  assert.equal(cut.nodes[0].pointIds.length,4);
  assert.equal(new Set(cut.nodes[0].pointIds).size,4,"fresh identities are unique");
  assert.equal(cut.nodes[1].pointIds.length,4);
  assert.equal(cut.nodes[0].pointIds[0],"a","a surviving vertex keeps its identity");
  assert.equal(constraintsValid(cut),true);
});

test("a line that misses, an unsplittable piece and a locked preset are refused", async () => {
  const {splitPolygonByLine, cutNodesByLine, createRect, createPreset} = await import("../../src/frontend/js/drawings/scene.js");
  const square=[[0,0],[100,0],[100,100],[0,100]];
  assert.equal(splitPolygonByLine(square,{point:[500,0],direction:[0,1]}),null,"a miss");
  assert.equal(splitPolygonByLine(square,{point:[50,0],direction:[0,0]}),null,"no direction");
  assert.equal(splitPolygonByLine(square,{point:[50,NaN],direction:[0,1]}),null,"non-finite");
  // A line just outside a vertex would leave a piece with no area.
  assert.equal(splitPolygonByLine(square,{point:[100,0],direction:[0,1]}),null,"touching the edge");

  const locked=sceneWith([createPreset("square",[0,0],[100,100])]);
  assert.equal(cutNodesByLine(locked,[locked.nodes[0].id],{point:[50,0],direction:[0,1]}),null,"locked");
  const free=sceneWith([{...createRect("Box",[0,0],[100,100]),id:"box"}]);
  assert.equal(cutNodesByLine(free,[],{point:[50,0],direction:[0,1]}),null,"nothing selected");
  assert.equal(cutNodesByLine(free,["box"],{point:[500,0],direction:[0,1]}),null,"the line misses every node");
});

test("a U cut across its own arms is refused instead of inventing a piece", async () => {
  const {splitPolygonByLine} = await import("../../src/frontend/js/drawings/scene.js");
  const u=[[0,0],[100,0],[100,100],[80,100],[80,20],[20,20],[20,100],[0,100]];
  const across=splitPolygonByLine(u,{point:[0,60],direction:[1,0]});
  assert.equal(across,null);
});

test("cubic insertion preserves sampled geometry and stable endpoints, linked tangents remain opposite", async () => {
  const {insertPathAnchor, setPathAnchorMode, moveCurvePoint, createPath, pathHandles, pathCommands} = await import("../../src/frontend/js/drawings/scene.js");
  const node=createPath("Curve","M0 0 C0 100 100 100 100 0");
  const inserted=insertPathAnchor(node,1,0,0.5);
  assert.ok(inserted);
  assert.equal(pathHandles(inserted.d).filter(h=>!h.control).length,3);
  assert.equal(inserted.pointIds[0],node.pointIds[0]);
  assert.equal(inserted.pointIds.at(-1),node.pointIds.at(-1));
  const before = pathPoints(node.d), after = pathPoints(inserted.d);
  before.forEach((point,index) => point.forEach((value,axis) => assert.ok(Math.abs(value-after[index*2][axis]) < 1e-6)));
  const cmds=pathCommands(inserted.d);
  assert.deepEqual(cmds[1].numbers.slice(4,6),[50,75]);
  const mode=setPathAnchorMode(inserted,inserted.pointIds[3],"symmetric");
  const moved=moveCurvePoint(mode,1,2,[30,90]);
  assert.deepEqual(pathCommands(moved.d)[1].numbers.slice(6,8),[70,60]);
});
