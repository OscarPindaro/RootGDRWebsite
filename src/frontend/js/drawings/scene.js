/* The scene document: creation, lookup, mutation and undo history.

   Every function is pure on the document it is given (it clones before
   mutating) so a caller can hold the previous value as an undo snapshot. The
   document is the same shape the server stores and validates; the client never
   invents a field the API would refuse. */

import { apply, bounds, centerOf, distanceToSegment, invert, multiply, pointInPolygon, polygonArea } from "./geometry.js";

let sequence = 0;

export function newId(prefix = "n") {
  sequence += 1;
  return `${prefix}-${sequence.toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

export function cloneScene(scene) {
  return JSON.parse(JSON.stringify(scene));
}

/** Visit every node in the tree, depth first, in drawing order. */
export function walk(nodes, visit, parent = null) {
  nodes.forEach((node, index) => {
    visit(node, nodes, index, parent);
    if (node.kind === "group") walk(node.nodes, visit, node);
  });
}

export function findNode(scene, id) {
  let found = null;
  walk(scene.nodes, (node, siblings, index, parent) => {
    if (node.id === id) found = { node, siblings, index, parent };
  });
  return found;
}

export function countNodes(scene) {
  let total = 0;
  walk(scene.nodes, () => { total += 1; });
  return total;
}

export function worldPoints(node) {
  return node.points.map((point) => apply(node.transform, point));
}

export function nodeBounds(node) {
  if (node.kind === "ellipse") {
    return { minX: node.cx - node.rx, minY: node.cy - node.ry, maxX: node.cx + node.rx, maxY: node.cy + node.ry };
  }
  if (node.kind === "path") {
    return bounds(pathPoints(node.d));
  }
  return bounds(node.points);
}

export function nodeCenter(node) {
  if (node.kind === "ellipse") return [node.cx, node.cy];
  if (node.kind === "path") return centerOf(pathPoints(node.d));
  return centerOf(node.points);
}

/* ---------- path parsing (absolute M/L/C/Z) ---------- */

export function pathCommands(d) {
  const commands = [];
  const matches = String(d).toUpperCase().matchAll(/([MLCZ])([^MLCZ]*)/g);
  for (const match of matches) {
    const numbers = (match[2].replace(/,/g, " ").match(/-?\d*\.?\d+/g) || []).map(Number);
    commands.push({ name: match[1], numbers });
  }
  return commands;
}

/** The path as a polyline, curves flattened: enough to hit-test and to bound. */
export function pathPoints(d) {
  const points = [];
  let current = [0, 0];
  let start = [0, 0];
  for (const { name, numbers } of pathCommands(d)) {
    if (name === "M" || name === "L") {
      for (let i = 0; i < numbers.length; i += 2) {
        current = [numbers[i], numbers[i + 1]];
        points.push(current);
      }
      if (name === "M") start = current;
    } else if (name === "C") {
      for (let i = 0; i < numbers.length; i += 6) {
        const control1 = [numbers[i], numbers[i + 1]];
        const control2 = [numbers[i + 2], numbers[i + 3]];
        const end = [numbers[i + 4], numbers[i + 5]];
        for (let step = 1; step <= 12; step += 1) {
          const t = step / 12;
          const u = 1 - t;
          points.push([
            u * u * u * current[0] + 3 * u * u * t * control1[0] + 3 * u * t * t * control2[0] + t * t * t * end[0],
            u * u * u * current[1] + 3 * u * u * t * control1[1] + 3 * u * t * t * control2[1] + t * t * t * end[1],
          ]);
        }
        current = end;
      }
    } else if (name === "Z") {
      points.push(start);
      current = start;
    }
  }
  return points;
}

/* ---------- hit testing ---------- */

/** The topmost node under a world point, or null. */
export function nodeAt(scene, worldPoint, tolerance = 6) {
  let hit = null;
  walk(scene.nodes, (node) => {
    if (node.visible === false) return;
    const inverse = invert(node.transform);
    if (!inverse) return;
    const local = apply(inverse, worldPoint);
    if (localHit(node, local, tolerance)) hit = node;
  });
  return hit;
}

function localHit(node, point, tolerance) {
  if (node.kind === "polygon") {
    if (node.fill && pointInPolygon(point, node.points)) return true;
    return edgesOf(node).some(([a, b]) => distanceToSegment(point, a, b) <= tolerance);
  }
  if (node.kind === "ellipse") {
    const dx = (point[0] - node.cx) / node.rx;
    const dy = (point[1] - node.cy) / node.ry;
    return dx * dx + dy * dy <= 1.15;
  }
  if (node.kind === "path") {
    const points = pathPoints(node.d);
    for (let i = 1; i < points.length; i += 1) {
      if (distanceToSegment(point, points[i - 1], points[i]) <= tolerance) return true;
    }
    return false;
  }
  return false;
}

/** The visible outline segments of a polygon as [from, to] pairs. */
export function edgesOf(node) {
  const points = node.points;
  const visible = node.edgeVisible;
  const edges = [];
  for (let index = 0; index < points.length; index += 1) {
    const shown = !visible || visible[index] !== false;
    if (shown) edges.push([points[index], points[(index + 1) % points.length]]);
  }
  return edges;
}

/* ---------- creation ---------- */

const DEFAULT_STROKE = "#17150f";

export function createPolygon(name, points, fill = "#e0a327") {
  return {
    kind: "polygon",
    id: newId("poly"),
    name,
    transform: [1, 0, 0, 1, 0, 0],
    opacity: 1,
    visible: true,
    fill,
    stroke: DEFAULT_STROKE,
    strokeWidth: 4,
    points,
    edgeVisible: null,
  };
}

export function createEllipse(name, center, rx, ry, fill = "#e0a327") {
  return {
    kind: "ellipse",
    id: newId("ell"),
    name,
    transform: [1, 0, 0, 1, 0, 0],
    opacity: 1,
    visible: true,
    fill,
    stroke: DEFAULT_STROKE,
    strokeWidth: 4,
    cx: center[0],
    cy: center[1],
    rx,
    ry,
  };
}

export function createPath(name, d, stroke = DEFAULT_STROKE) {
  return {
    kind: "path",
    id: newId("path"),
    name,
    transform: [1, 0, 0, 1, 0, 0],
    opacity: 1,
    visible: true,
    fill: null,
    stroke,
    strokeWidth: 4,
    d,
  };
}

/** A rectangle as a four-point polygon, so it edits like any other shape. */
export function createRect(name, from, to, fill = "#e0a327") {
  const [x1, y1] = from;
  const [x2, y2] = to;
  return createPolygon(
    name,
    [
      [Math.min(x1, x2), Math.min(y1, y2)],
      [Math.max(x1, x2), Math.min(y1, y2)],
      [Math.max(x1, x2), Math.max(y1, y2)],
      [Math.min(x1, x2), Math.max(y1, y2)],
    ],
    fill
  );
}

/* ---------- mutation ---------- */

export function addNode(scene, node, parentId = null) {
  const next = cloneScene(scene);
  const parent = parentId ? findNode(next, parentId) : null;
  const list = parent && parent.node.kind === "group" ? parent.node.nodes : next.nodes;
  list.push(node);
  return next;
}

export function removeNode(scene, id) {
  const next = cloneScene(scene);
  const found = findNode(next, id);
  if (!found) return next;
  found.siblings.splice(found.index, 1);
  return next;
}

export function duplicateNode(scene, id) {
  const next = cloneScene(scene);
  const found = findNode(next, id);
  if (!found) return next;
  const copy = cloneScene(found.node);
  const renamed = renameIds(copy, found.node.name);
  renamed.transform = multiply([1, 0, 0, 1, 16, 16], renamed.transform);
  found.siblings.splice(found.index + 1, 0, renamed);
  return { scene: next, id: renamed.id };
}

function renameIds(node, name) {
  node.id = newId(node.kind);
  node.name = `${name} copia`;
  if (node.kind === "group") node.nodes.forEach((child) => renameIds(child, child.name));
  return node;
}

/** Move a node one step towards the front (delta > 0) or the back. */
export function reorderNode(scene, id, delta) {
  const next = cloneScene(scene);
  const found = findNode(next, id);
  if (!found) return next;
  const target = Math.max(0, Math.min(found.siblings.length - 1, found.index + delta));
  if (target === found.index) return next;
  const [node] = found.siblings.splice(found.index, 1);
  found.siblings.splice(target, 0, node);
  return next;
}

export function patchNode(scene, id, patch) {
  const next = cloneScene(scene);
  const found = findNode(next, id);
  if (!found) return next;
  Object.assign(found.node, patch);
  return next;
}

export function setTransform(scene, id, matrix) {
  return patchNode(scene, id, { transform: matrix });
}

export function validPolygon(points) {
  return points.length >= 3 && polygonArea(points) > 1e-6;
}

/* ---------- history ---------- */

export class History {
  constructor(scene, limit = 60) {
    this.limit = limit;
    this.past = [];
    this.future = [];
    this.present = cloneScene(scene);
  }

  /** Record a completed change: one call per gesture, never per pointer move. */
  commit(scene) {
    const value = cloneScene(scene);
    if (JSON.stringify(value) === JSON.stringify(this.present)) return;
    this.past.push(this.present);
    if (this.past.length > this.limit) this.past.shift();
    this.present = value;
    this.future = [];
  }

  undo() {
    if (!this.past.length) return this.present;
    this.future.push(this.present);
    this.present = this.past.pop();
    return this.present;
  }

  redo() {
    if (!this.future.length) return this.present;
    this.past.push(this.present);
    this.present = this.future.pop();
    return this.present;
  }

  get canUndo() {
    return this.past.length > 0;
  }

  get canRedo() {
    return this.future.length > 0;
  }
}
