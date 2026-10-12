/* The scene document: creation, lookup, mutation and undo history.

   Every function is pure on the document it is given (it clones before
   mutating) so a caller can hold the previous value as an undo snapshot. The
   document is the same shape the server stores and validates; the client never
   invents a field the API would refuse. */

import { apply, bounds, centerOf, distanceToSegment, invert, multiply, pointInPolygon, polygonArea, translation, rotateAbout } from "./geometry.js";

/** The deepest nesting the document format accepts. */
export const MAX_DEPTH = 8;

let sequence = 0;

export function newId(prefix = "n") {
  sequence += 1;
  return `${prefix}-${sequence.toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

export function cloneScene(scene) {
  return JSON.parse(JSON.stringify(scene));
}

export function migrateScene(scene) {
  const next = cloneScene(scene);
  if (![1, 2, 3, 4, 5].includes(next.schemaVersion)) throw new Error("Unsupported native drawing version");
  next.schemaVersion = 5;
  walk(next.nodes, node => {
    node.pivot ??= null;
    node.editLocked ??= false;
    node.anchors ??= [];
    if (node.kind !== "group") node.constraint ??= null;
    if (node.kind === "polygon") node.pointIds ??= node.points.map((_, index) => `v${index}`);
    if (node.kind === "path") { node.pointIds ??= pathHandles(node.d).map((_, index) => `h${index}`); node.anchorModes ??= []; }
  });
  return next;
}

export function lockedPolygon(points, kind) {
  if (kind === "circle") return false;
  const edges = points.map((point, i) => [points[(i + 1) % points.length][0] - point[0], points[(i + 1) % points.length][1] - point[1]]);
  const lengths = edges.map(([x, y]) => x * x + y * y);
  const equal = (a, b) => Math.abs(a - b) <= Math.max(1e-8, 1e-6 * Math.max(Math.abs(a), Math.abs(b)));
  const perpendicular = (a, b) => Math.abs(a[0] * b[0] + a[1] * b[1]) <= 1e-6 * Math.hypot(...a) * Math.hypot(...b);
  if (kind.startsWith("triangle_")) {
    if (points.length !== 3) return false;
    if (kind === "triangle_isosceles") return equal(lengths[1], lengths[2]);
    if (kind === "triangle_equilateral") return lengths.every(length => equal(length, lengths[0]));
    const corner = kind === "triangle_right_right" ? 1 : 0;
    return perpendicular(edges[corner], edges[(corner + 2) % 3]);
  }
  if (kind === "rectangle" || kind === "square") {
    return points.length === 4 && edges.every((edge, i) => perpendicular(edge, edges[(i + 1) % 4])) && (kind === "rectangle" || equal(lengths[0], lengths[1]));
  }
  const center = points.reduce((sum, point) => [sum[0] + point[0] / points.length, sum[1] + point[1] / points.length], [0, 0]);
  const radii = points.map(point => (point[0] - center[0]) ** 2 + (point[1] - center[1]) ** 2);
  return kind === "regular_polygon" && lengths.every(length => equal(length, lengths[0])) && radii.every(radius => equal(radius, radii[0]));
}

export function constraintsValid(scene) {
  let valid = true;
  walk(scene.nodes, node => {
    const [a, b, c, d] = node.transform;
    valid &&= node.transform.every(value => Number.isFinite(value) && Math.abs(value) <= 100000) && Math.abs(a * d - b * c) >= 1e-9;
    if (!node.constraint) return;
    const world = nodeFrame(scene, node.id).world;
    if (node.kind === "polygon") {
      valid &&= lockedPolygon(node.points, node.constraint.kind) && lockedPolygon(node.points.map(point => apply(world, point)), node.constraint.kind);
    } else if (node.kind === "ellipse" && node.constraint.kind === "circle") {
      const [a, b, c, d] = world;
      const first = a * a + b * b, second = c * c + d * d;
      valid &&= Math.abs(node.rx - node.ry) <= 1e-6 * Math.max(node.rx, node.ry) && Math.abs(first - second) <= 1e-6 * Math.max(first, second) && Math.abs(a * c + b * d) <= 1e-6 * first;
    } else valid = false;
  });
  return valid;
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

export function editLocked(scene, id) {
  let current = findNode(scene,id);
  while (current) {
    if (current.node.editLocked) return true;
    current = current.parent ? findNode(scene,current.parent.id) : null;
  }
  return false;
}

export function editableSelection(scene, ids) {
  return ids.every(id => {
    const found = findNode(scene,id);
    if (!found || editLocked(scene,id)) return false;
    let locked = false;
    if (found.node.kind === "group") walk(found.node.nodes, node => { locked ||= Boolean(node.editLocked); });
    return !locked;
  });
}

export function visibilityIssues(scene, id) {
  const found = findNode(scene, id);
  if (!found) return ["no-selection"];
  const node = found.node, issues = [];
  if (!node.visible) issues.push("hidden");
  let parent = found.parent, hiddenParent = false, opacity = node.opacity;
  while (parent) {
    hiddenParent ||= !parent.visible;
    opacity *= parent.opacity;
    parent = findNode(scene, parent.id).parent;
  }
  if (hiddenParent) issues.push("hidden-parent");
  if (!opacity) issues.push("zero-opacity");
  if (node.kind === "group") {
    if (!node.nodes.length) issues.push("empty-group");
  } else if (!node.fill && (!node.stroke || !node.strokeWidth || (node.kind === "polygon" && node.edgeVisible?.every(value => !value)))) issues.push("no-paint");
  return issues;
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
  if (node.kind === "group") {
    const boxes = node.nodes.map((child) => {
      const box = nodeBounds(child);
      const corners = [
        [box.minX, box.minY],
        [box.maxX, box.minY],
        [box.maxX, box.maxY],
        [box.minX, box.maxY],
      ].map((point) => apply(child.transform, point));
      return bounds(corners);
    });
    if (!boxes.length) return { minX: 0, minY: 0, maxX: 0, maxY: 0 };
    return boxes.reduce((acc, box) => ({
      minX: Math.min(acc.minX, box.minX),
      minY: Math.min(acc.minY, box.minY),
      maxX: Math.max(acc.maxX, box.maxX),
      maxY: Math.max(acc.maxY, box.maxY),
    }));
  }
  if (node.kind === "ellipse") {
    return { minX: node.cx - node.rx, minY: node.cy - node.ry, maxX: node.cx + node.rx, maxY: node.cy + node.ry };
  }
  if (node.kind === "path") {
    return bounds(pathPoints(node.d));
  }
  return bounds(node.points);
}

export function selectionCorners(scene, ids) {
  const corners = ids.flatMap(id => {
    const frame = nodeFrame(scene, id);
    const box = nodeBounds(frame.node);
    return [[box.minX, box.minY], [box.maxX, box.minY], [box.maxX, box.maxY], [box.minX, box.maxY]].map(point => apply(frame.world, point));
  });
  if (ids.length === 1) return corners;
  const box = bounds(corners);
  return [[box.minX, box.minY], [box.maxX, box.minY], [box.maxX, box.maxY], [box.minX, box.maxY]];
}

export function nodeCenter(node) {
  const box = nodeBounds(node);
  return [(box.minX + box.maxX) / 2, (box.minY + box.maxY) / 2];
}

/* ---------- path parsing (absolute M/L/C/Z) ---------- */

export function pathHandles(d) {
  const handles = [];
  let previous = null, previousIndex = null;
  let controlNumber = 0;
  pathCommands(d).forEach((command, index) => {
    for (let offset = 0; offset < command.numbers.length; offset += 2) {
      const point = command.numbers.slice(offset, offset + 2);
      const control = command.name === "C" && offset % 6 !== 4;
      const endOffset = Math.floor(offset / 6) * 6 + 4;
      const anchor = control ? (offset % 6 === 0 ? previous : command.numbers.slice(endOffset, endOffset + 2)) : null;
      const anchorIndex = control ? (offset % 6 === 0 ? previousIndex : handles.length + 1) : null;
      handles.push({ command: index, offset, point, control, anchor, anchorIndex, label: control ? `Controllo ${++controlNumber}` : "Punto del tracciato" });
      if (!control) { previous = point; previousIndex = handles.length - 1; }
    }
  });
  const endpoints = handles.filter(handle => !handle.control);
  if (endpoints.length) endpoints[0].label = "Punto iniziale";
  if (endpoints.length > 1) endpoints[endpoints.length - 1].label = "Punto finale";
  return handles;
}

export function movePathPoint(d, commandIndex, offset, point) {
  const commands = pathCommands(d);
  commands[commandIndex].numbers.splice(offset, 2, ...point);
  return commands.map(c => c.name + c.numbers.map(n => Math.round(n * 1000) / 1000).join(" ")).join(" ");
}

export function moveCurvePoint(node, command, offset, point) {
  const handles = pathHandles(node.d), index = handles.findIndex(handle => handle.command === command && handle.offset === offset);
  if (index < 0 || !point.every(Number.isFinite)) return null;
  const commands = pathCommands(node.d), handle = handles[index];
  commands[command].numbers.splice(offset,2,...point);
  if (!handle.control) {
    const delta = point.map((value,axis) => value - handle.point[axis]);
    handles.filter(control => control.control && control.anchorIndex === index).forEach(control => commands[control.command].numbers.splice(control.offset,2,...control.point.map((value,axis) => value + delta[axis])));
  } else {
    const mode = node.anchorModes?.find(mode => mode.id === node.pointIds[handle.anchorIndex])?.mode || "corner";
    const opposite = handles.find((control,position) => position !== index && control.control && control.anchorIndex === handle.anchorIndex);
    if (opposite && mode !== "corner") {
      const anchor = handles[handle.anchorIndex].point, vector = point.map((value,axis) => value - anchor[axis]), length = Math.hypot(...vector);
      const distance = mode === "symmetric" ? length : Math.hypot(...opposite.point.map((value,axis) => value - anchor[axis]));
      if (length) commands[opposite.command].numbers.splice(opposite.offset,2,...anchor.map((value,axis) => value - vector[axis] / length * distance));
      else if (mode === "symmetric") commands[opposite.command].numbers.splice(opposite.offset,2,...anchor);
    }
  }
  const d = commands.map(c => c.name + c.numbers.map(n => Math.round(n * 1e6) / 1e6).join(" ")).join(" ");
  return d.length <= 8000 && commands.every(command => command.numbers.every(value => Number.isFinite(value) && Math.abs(value) <= 100000)) ? {...node,d} : null;
}

export function setPathAnchorMode(node, id, mode) {
  if (!["corner", "smooth", "symmetric"].includes(mode)) return null;
  const handles = pathHandles(node.d), index = node.pointIds.indexOf(id);
  if (!handles[index] || handles[index].control) return null;
  const next = {...node, anchorModes:[...(node.anchorModes || []).filter(entry => entry.id !== id),{id,mode}]};
  const control = handles.find(handle => handle.control && handle.anchorIndex === index);
  return control && mode !== "corner" ? moveCurvePoint(next,control.command,control.offset,control.point) : next;
}

export function insertPathAnchor(node, command, offset = 0, t = 0.5) {
  const commands = pathCommands(node.d), target = commands[command];
  if (!target || target.name !== "C" || !Number.isInteger(offset) || offset < 0 || offset % 6 !== 0 || !Number.isFinite(t) || t <= 0 || t >= 1 || target.numbers.length < offset + 6) return null;
  const handles = pathHandles(node.d), first = handles.findIndex(handle => handle.command === command && handle.offset === offset);
  const p0 = handles[handles[first].anchorIndex].point, p1 = target.numbers.slice(offset,offset+2), p2 = target.numbers.slice(offset+2,offset+4), p3 = target.numbers.slice(offset+4,offset+6);
  const mix = (a,b) => a.map((value,axis) => value + (b[axis] - value) * t);
  const a = mix(p0,p1), b = mix(p1,p2), c = mix(p2,p3), d = mix(a,b), e = mix(b,c), middle = mix(d,e);
  target.numbers.splice(offset,6,...a,...d,...middle,...e,...c,...p3);
  const pointIds = [...node.pointIds], midId = newId("h");
  pointIds.splice(first,3,node.pointIds[first],newId("h"),midId,newId("h"),node.pointIds[first+1],node.pointIds[first+2]);
  const path = commands.map(c => c.name + c.numbers.map(n => Math.round(n * 1e6) / 1e6).join(" ")).join(" ");
  return path.length <= 8000 && pointIds.length <= 3072 && (node.anchorModes || []).length < 512 ? {...node, pointIds, anchorModes:[...(node.anchorModes || []),{id:midId,mode:"smooth"}], d:path} : null;
}

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
export function nodeFrame(scene, id) {
  function visit(nodes, parent) {
    for (const node of nodes) {
      const world = multiply(parent, node.transform);
      if (node.id === id) return { node, parent, world };
      if (node.kind === "group") {
        const found = visit(node.nodes, world);
        if (found) return found;
      }
    }
    return null;
  }
  return visit(scene.nodes, [1, 0, 0, 1, 0, 0]);
}

export function nodeAt(scene, worldPoint, tolerance = 6) {
  let hit = null;
  function visit(nodes, parent) {
    for (const node of nodes) {
      if (node.visible === false || node.opacity === 0 || node.editLocked) continue;
      const world = multiply(parent, node.transform);
      if (node.kind === "group") {
        visit(node.nodes, world);
        continue;
      }
      const inverse = invert(world);
      if (!inverse) continue;
      const local = apply(inverse, worldPoint);
      const scale = Math.max(Math.hypot(world[0], world[1]), Math.hypot(world[2], world[3]));
      if (localHit(node, local, tolerance / scale)) hit = node;
    }
  }
  visit(scene.nodes, [1, 0, 0, 1, 0, 0]);
  return hit;
}

function localHit(node, point, tolerance) {
  if (node.kind === "polygon") {
    if (node.fill && pointInPolygon(point, node.points)) return true;
    return Boolean(node.stroke && node.strokeWidth > 0 && edgesOf(node).some(([a, b]) => distanceToSegment(point, a, b) <= tolerance));
  }
  if (node.kind === "ellipse") {
    const dx = (point[0] - node.cx) / node.rx;
    const dy = (point[1] - node.cy) / node.ry;
    const radius = Math.hypot(dx, dy);
    return Boolean((node.fill && radius <= 1) || (node.stroke && node.strokeWidth > 0 && Math.abs(radius - 1) <= tolerance / Math.min(node.rx, node.ry)));
  }
  if (node.kind === "path") {
    const points = pathPoints(node.d);
    if (node.fill && pointInPolygon(point, points)) return true;
    if (!node.stroke || node.strokeWidth <= 0) return false;
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
    pointIds: points.map(() => newId("v")),
    pivot: null,
    editLocked: false,
    anchors: [],
    constraint: null,
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
    pivot: null,
    editLocked: false,
    anchors: [],
    constraint: null,
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
    pointIds: pathHandles(d).map(() => newId("h")),
    anchorModes: [],
    pivot: null,
    editLocked: false,
    anchors: [],
    constraint: null,
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

export function createPreset(kind, from, to, sides = 6) {
  let width = Math.abs(to[0] - from[0]), height = Math.abs(to[1] - from[1]);
  const x = Math.min(from[0], to[0]), y = Math.min(from[1], to[1]);
  if (![x, y, width, height].every(Number.isFinite) || width < 0.1 || height < 0.1) return null;
  let node;
  if (kind === "circle" || kind === "ellipse") {
    const radius = Math.min(width, height) / 2;
    node = createEllipse(kind === "circle" ? "Cerchio" : "Ellisse", [x + width / 2, y + height / 2], kind === "circle" ? radius : width / 2, kind === "circle" ? radius : height / 2);
  } else if (kind === "rectangle" || kind === "square") {
    if (kind === "square") width = height = Math.min(width, height);
    node = createRect(kind === "square" ? "Quadrato" : "Rettangolo", [x, y], [x + width, y + height]);
  } else if (kind.startsWith("triangle_")) {
    if (kind === "triangle_equilateral") {
      width = Math.min(width, 2 * height / Math.sqrt(3));
      height = width * Math.sqrt(3) / 2;
    }
    const tip = kind === "triangle_right_right" ? x + width : kind === "triangle_right_left" ? x : x + width / 2;
    node = createPolygon("Triangolo", [[x, y + height], [x + width, y + height], [tip, y]]);
  } else if (kind === "regular_polygon") {
    if (!Number.isInteger(sides) || sides < 3 || sides > 32) return null;
    const radius = Math.min(width, height) / 2;
    node = createPolygon("Poligono regolare", Array.from({length:sides}, (_, index) => {
      const angle = -Math.PI / 2 + 2 * Math.PI * index / sides;
      return [x + width / 2 + radius * Math.cos(angle), y + height / 2 + radius * Math.sin(angle)];
    }));
  } else return null;
  node.constraint = kind === "ellipse" ? null : {kind};
  return node;
}

export function editPresetVertex(node, index, point) {
  const kind = node.constraint?.kind;
  if (!kind) return node.points.map((entry, i) => i === index ? point : entry);
  const points = node.points.map(entry => [...entry]);
  if (kind === "triangle_isosceles") {
    if (index === 2) points[2] = [(points[0][0] + points[1][0]) / 2, point[1]];
    else {
      const center = points[2][0], half = Math.abs(point[0] - center);
      points[0] = [center - half, point[1]];
      points[1] = [center + half, point[1]];
    }
    return validPolygon(points) ? points : node.points;
  }
  if (kind === "rectangle" || kind === "square") {
    const opposite = points[(index + 2) % 4];
    const regenerated = createPreset(kind, opposite, point);
    return regenerated?.points || node.points;
  }
  if (kind === "triangle_right_right" || kind === "triangle_right_left") {
    if (index === 2) points[2][1] = point[1];
    else {
      const delta = point[0] - points[index][0];
      points[index][0] += delta;
      if ((kind === "triangle_right_right" && index === 1) || (kind === "triangle_right_left" && index === 0)) points[2][0] += delta;
      points[0][1] = points[1][1] = point[1];
    }
    return validPolygon(points) && lockedPolygon(points, kind) ? points : node.points;
  }
  const center = nodeCenter(node), original = points[index];
  const before = Math.hypot(original[0] - center[0], original[1] - center[1]);
  const after = Math.hypot(point[0] - center[0], point[1] - center[1]);
  if (after < 0.1 || !before) return node.points;
  return points.map(entry => [center[0] + (entry[0] - center[0]) * after / before, center[1] + (entry[1] - center[1]) * after / before]);
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
  node.name = `${name.slice(0, 113)} copia`;
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
  return constraintsValid(next) ? next : scene;
}

export function setTransform(scene, id, matrix) {
  return patchNode(scene, id, { transform: matrix });
}

export function transformInWorld(scene, id, delta, original = nodeFrame(scene, id).world) {
  return transformNodesInWorld(scene, [{id, transform:original}], delta);
}

export function transformNodesInWorld(scene, entries, delta) {
  if (!editableSelection(scene,entries.map(entry => entry.id))) return scene;
  const next = cloneScene(scene);
  for (const {id, transform} of entries) {
    const frame = nodeFrame(next, id);
    const inverse = frame && invert(frame.parent);
    if (!inverse) return scene;
    findNode(next, id).node.transform = multiply(inverse, multiply(delta, transform));
  }
  return constraintsValid(next) ? next : scene;
}

export function geometryInfo(scene, ids) {
  if (!ids.length || ids.some(id => !findNode(scene, id))) return null;
  const corners = selectionCorners(scene, ids), frame = nodeFrame(scene, ids[0]);
  const pivot = ids.length === 1 ? frame.node.pivot || nodeCenter(frame.node) : [(corners[0][0] + corners[2][0]) / 2, (corners[0][1] + corners[2][1]) / 2];
  return {x:corners[0][0], y:corners[0][1], width:Math.hypot(corners[1][0] - corners[0][0], corners[1][1] - corners[0][1]), height:Math.hypot(corners[3][0] - corners[0][0], corners[3][1] - corners[0][1]), angle:Math.atan2(corners[1][1] - corners[0][1], corners[1][0] - corners[0][0]) * 180 / Math.PI, pivotX:pivot[0], pivotY:pivot[1]};
}

export function editGeometry(scene, ids, parameters) {
  const info = geometryInfo(scene, ids);
  if (!info || !parameters || Object.entries(parameters).some(([key, value]) => !["x", "y", "width", "height", "angle", "pivotX", "pivotY"].includes(key) || !Number.isFinite(value) || Math.abs(value) > 100000)) return null;
  if ((parameters.width !== undefined && (parameters.width <= 0 || !info.width)) || (parameters.height !== undefined && (parameters.height <= 0 || !info.height))) return null;
  let next = cloneScene(scene);
  if (parameters.pivotX !== undefined || parameters.pivotY !== undefined) {
    if (ids.length !== 1) return null;
    findNode(next, ids[0]).node.pivot = [parameters.pivotX ?? info.pivotX, parameters.pivotY ?? info.pivotY];
  }
  let sx = parameters.width !== undefined ? parameters.width / info.width : 1;
  let sy = parameters.height !== undefined ? parameters.height / info.height : 1;
  let ratioLocked = false;
  walk(next.nodes, node => {
    if (!["circle", "square", "triangle_equilateral", "regular_polygon"].includes(node.constraint?.kind)) return;
    let current = findNode(next, node.id);
    while (current) {
      if (ids.includes(current.node.id)) { ratioLocked = true; break; }
      current = current.parent ? findNode(next, current.parent.id) : null;
    }
  });
  if (ratioLocked && parameters.width !== undefined && parameters.height !== undefined && Math.abs(sx - sy) > 1e-6) return null;
  if (ratioLocked && parameters.width !== undefined && parameters.height === undefined) sy = sx;
  if (ratioLocked && parameters.height !== undefined && parameters.width === undefined) sx = sy;
  const corners = selectionCorners(next, ids), frame = nodeFrame(next, ids[0]);
  const pivot = ids.length === 1 ? apply(frame.world, frame.node.pivot || nodeCenter(frame.node)) : [(corners[0][0] + corners[2][0]) / 2, (corners[0][1] + corners[2][1]) / 2];
  const u = [corners[1][0] - corners[0][0], corners[1][1] - corners[0][1]], v = [corners[3][0] - corners[0][0], corners[3][1] - corners[0][1]];
  if (!info.width && !info.height) { u[0] = 1; v[1] = 1; }
  else {
    if (!info.width) { u[0] = v[1] / info.height; u[1] = -v[0] / info.height; }
    if (!info.height) { v[0] = -u[1] / info.width; v[1] = u[0] / info.width; }
  }
  const basis = [u[0], u[1], v[0], v[1], pivot[0], pivot[1]], inverse = invert(basis);
  if (!inverse && (parameters.width !== undefined || parameters.height !== undefined)) return null;
  const scale = inverse ? multiply(basis, multiply([sx,0,0,sy,0,0], inverse)) : [1,0,0,1,0,0];
  const delta = multiply(rotateAbout(pivot, ((parameters.angle ?? info.angle) - info.angle) * Math.PI / 180), scale);
  const entries = ids.map(id => ({id, transform:nodeFrame(next,id).world}));
  const transformed = transformNodesInWorld(next, entries, delta);
  if (transformed === next && (sx !== 1 || sy !== 1 || parameters.angle !== undefined)) return null;
  next = transformed;
  const after = geometryInfo(next, ids);
  const move = translation((parameters.x ?? after.x) - after.x, (parameters.y ?? after.y) - after.y);
  const moved = transformNodesInWorld(next, ids.map(id => ({id, transform:nodeFrame(next,id).world})), move);
  return moved === next && (move[4] || move[5]) ? null : constraintsValid(moved) ? moved : null;
}

export function alignNodes(scene, ids, alignment) {
  if (ids.length < (alignment?.startsWith("distribute") ? 3 : 2) || ids.some(id => !findNode(scene,id)) || !["left", "center-x", "right", "top", "center-y", "bottom", "distribute-x", "distribute-y"].includes(alignment)) return null;
  const boxes = ids.map(id => ({id, box:bounds(selectionCorners(scene,[id]))}));
  const total = bounds(boxes.flatMap(({box}) => [[box.minX,box.minY],[box.maxX,box.maxY]]));
  const next = cloneScene(scene);
  if (alignment.startsWith("distribute")) {
    const horizontal = alignment === "distribute-x", low = horizontal ? "minX" : "minY", high = horizontal ? "maxX" : "maxY";
    boxes.sort((a,b) => a.box[low] - b.box[low]);
    const widths = boxes.map(({box}) => box[high] - box[low]);
    const gap = (boxes.at(-1).box[high] - boxes[0].box[low] - widths.reduce((a,b) => a+b,0)) / (boxes.length - 1);
    let cursor = boxes[0].box[low];
    boxes.forEach((entry,index) => { entry.delta = horizontal ? [cursor - entry.box[low],0] : [0,cursor - entry.box[low]]; cursor += widths[index] + gap; });
  } else {
    boxes.forEach(entry => {
      const b = entry.box;
      entry.delta = [alignment === "left" ? total.minX - b.minX : alignment === "right" ? total.maxX - b.maxX : alignment === "center-x" ? (total.minX + total.maxX - b.minX - b.maxX) / 2 : 0, alignment === "top" ? total.minY - b.minY : alignment === "bottom" ? total.maxY - b.maxY : alignment === "center-y" ? (total.minY + total.maxY - b.minY - b.maxY) / 2 : 0];
    });
  }
  for (const {id, delta} of boxes) {
    const frame = nodeFrame(scene,id), inverse = invert(frame.parent);
    if (!inverse) return null;
    findNode(next,id).node.transform = multiply(inverse, multiply(translation(...delta), frame.world));
  }
  return constraintsValid(next) ? next : null;
}

export function validPolygon(points) {
  return points.length >= 3 && points.length <= 256 && points.every(p => p.every(Number.isFinite)) && polygonArea(points) > 1e-6 && isSimplePolygon(points);
}

/* ---------- grouping ---------- */

export function depthOf(nodes, id, depth = 1) {
  for (const node of nodes) {
    if (node.id === id) return depth;
    if (node.kind === "group") {
      const nested = depthOf(node.nodes, id, depth + 1);
      if (nested) return nested;
    }
  }
  return 0;
}

/**
 * Group sibling nodes into one new group.
 *
 * The group takes an identity transform, so every child keeps its own
 * transform and nothing moves: regrouping is a change of structure, not of
 * geometry. Only siblings are grouped, and the result must still fit the
 * format's nesting limit.
 */
export function groupNodes(scene, ids) {
  if (ids.length < 2) return null;
  const next = cloneScene(scene);
  const found = [];
  walk(next.nodes, (node, siblings, index) => {
    if (ids.includes(node.id)) found.push({ node, siblings, index });
  });
  if (found.length !== ids.length) return null;
  const siblings = found[0].siblings;
  if (!found.every((entry) => entry.siblings === siblings)) return null;
  const deepest = Math.max(...ids.map((id) => depthOf(next.nodes, id)));
  const height = node => node.kind === "group" ? 1 + Math.max(0, ...node.nodes.map(height)) : 0;
  if (deepest + Math.max(...found.map(entry => height(entry.node))) > MAX_DEPTH) return null;
  const positions = found.map(entry => entry.index).sort((a, b) => a - b);
  if (positions.some((position, i) => position !== positions[0] + i)) return null;

  const index = Math.min(...found.map((entry) => entry.index));
  const members = [...found]
    .sort((a, b) => a.index - b.index)
    .map((entry) => entry.node);
  for (const entry of [...found].sort((a, b) => b.index - a.index)) {
    siblings.splice(entry.index, 1);
  }
  const group = {
    kind: "group",
    id: newId("group"),
    name: "Gruppo",
    transform: [1, 0, 0, 1, 0, 0],
    opacity: 1,
    visible: true,
    nodes: members,
    pivot: null,
    editLocked: false,
    anchors: [],
  };
  siblings.splice(index, 0, group);
  return { scene: next, id: group.id };
}

/**
 * Dissolve a group into its children, in place.
 *
 * Each child's transform is composed with the group's, so the world position
 * is exactly what it was: ungrouping must not move anything.
 */
export function ungroupNode(scene, id) {
  const next = cloneScene(scene);
  const found = findNode(next, id);
  if (!found || found.node.kind !== "group") return null;
  const group = found.node;
  const children = group.nodes.map((child) => ({
    ...cloneScene(child),
    transform: multiply(group.transform, child.transform),
    opacity: group.opacity * child.opacity,
    visible: group.visible && child.visible,
  }));
  found.siblings.splice(found.index, 1, ...children);
  return constraintsValid(next) ? { scene: next, ids: children.map((child) => child.id) } : null;
}

export function reparentNode(scene, id, parentId = null) {
  const source = findNode(scene, id);
  const target = parentId ? findNode(scene, parentId) : null;
  if (!source || (parentId && (!target || target.node.kind !== "group"))) return null;
  const descendants = [];
  if (source.node.kind === "group") walk(source.node.nodes, node => descendants.push(node.id));
  if (parentId === id || descendants.includes(parentId)) return null;
  if ((source.parent?.id || null) === parentId) return {scene: cloneScene(scene), id};
  const world = nodeFrame(scene, id).world;
  const parentWorld = parentId ? nodeFrame(scene, parentId).world : [1, 0, 0, 1, 0, 0];
  const next = cloneScene(scene);
  const found = findNode(next, id);
  const [node] = found.siblings.splice(found.index, 1);
  node.transform = multiply(invert(parentWorld), world);
  const destination = parentId ? findNode(next, parentId).node.nodes : next.nodes;
  destination.push(node);
  const height = nodes => Math.max(0, ...nodes.map(n => n.kind === "group" ? 1 + height(n.nodes) : 0));
  if (height(next.nodes) > MAX_DEPTH || !constraintsValid(next)) return null;
  return {scene: next, id};
}

/* ---------- straight cut ---------- */

/** Do two segments cross, other than at a shared endpoint? */
function crosses(a1, a2, b1, b2) {
  const orientation = (p, q, r) => Math.sign((q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]));
  const onSegment = (p, q, r) =>
    Math.min(p[0], r[0]) <= q[0] && q[0] <= Math.max(p[0], r[0]) &&
    Math.min(p[1], r[1]) <= q[1] && q[1] <= Math.max(p[1], r[1]);
  const o1 = orientation(a1, a2, b1);
  const o2 = orientation(a1, a2, b2);
  const o3 = orientation(b1, b2, a1);
  const o4 = orientation(b1, b2, a2);
  if (o1 !== o2 && o3 !== o4) return true;
  if (o1 === 0 && onSegment(a1, b1, a2)) return true;
  if (o2 === 0 && onSegment(a1, b2, a2)) return true;
  if (o3 === 0 && onSegment(b1, a1, b2)) return true;
  if (o4 === 0 && onSegment(b1, a2, b2)) return true;
  return false;
}

/** A simple polygon: no two non-adjacent edges cross. */
export function isSimplePolygon(points) {
  const n = points.length;
  if (new Set(points.map(p => p.join(","))).size !== n) return false;
  for (let i = 0; i < n; i += 1) {
    for (let j = i + 1; j < n; j += 1) {
      const adjacent = j === i + 1 || (i === 0 && j === n - 1);
      if (adjacent) continue;
      if (crosses(points[i], points[(i + 1) % n], points[j], points[(j + 1) % n])) return false;
    }
  }
  return true;
}

/**
 * Split a polygon along the chord between vertices i and j.
 *
 * Returns `{a, b}` (each with its own points and the source edge indices) or
 * null when the cut is not a real split: adjacent or coincident endpoints, a
 * chord that leaves the polygon, or a piece with no area. The caller keeps the
 * original node for `a` and adds a new one for `b`.
 */
export function splitPolygonAt(points, i, j) {
  const n = points.length;
  if (!Number.isInteger(i) || !Number.isInteger(j) || i < 0 || j < 0 || i >= n || j >= n) return null;
  if (!validPolygon(points) || n < 4) return null;
  if (i === j) return null;
  const adjacent = (i + 1) % n === j || (j + 1) % n === i;
  if (adjacent) return null;

  const walk = (from, to) => {
    const chain = [];
    for (let k = from; ; k = (k + 1) % n) {
      chain.push(k);
      if (k === to) break;
    }
    return chain;
  };
  const aIndices = walk(i, j);
  const bIndices = walk(j, i);
  if (aIndices.length < 3 || bIndices.length < 3) return null;

  const aPoints = aIndices.map((index) => points[index]);
  const bPoints = bIndices.map((index) => points[index]);
  if (!validPolygon(aPoints) || !validPolygon(bPoints)) return null;
  if (!isSimplePolygon(aPoints) || !isSimplePolygon(bPoints)) return null;

  // The chord must stay inside the source polygon: sample it, endpoints aside.
  for (let step = 1; step < 9; step += 1) {
    const t = step / 9;
    const point = [
      points[i][0] + (points[j][0] - points[i][0]) * t,
      points[i][1] + (points[j][1] - points[i][1]) * t,
    ];
    if (!pointInPolygon(point, points)) return null;
  }
  return { aIndices, bIndices, aPoints, bPoints };
}

/** The cut edges are hidden: the two pieces still read as one silhouette. */
function cutVisibility(sourceVisible, indices) {
  return indices.map((index, position) =>
    position === indices.length - 1 ? false : !sourceVisible || sourceVisible[index] !== false
  );
}

/**
 * Apply a cut to a polygon node: the original keeps the `a` piece and its id,
 * and the `b` piece becomes a sibling right after it. One document, one undo.
 */
export function cutNode(scene, id, i, j) {
  const found = findNode(scene, id);
  if (!found || found.node.kind !== "polygon" || found.node.constraint) return null;
  const node = found.node;
  const split = splitPolygonAt(node.points, i, j);
  if (!split) return null;

  const next = cloneScene(scene);
  const target = findNode(next, id);
  target.node.points = split.aPoints.map(p => [...p]);
  if (node.pointIds) target.node.pointIds = split.aIndices.map(index => node.pointIds[index]);
  target.node.edgeVisible = cutVisibility(node.edgeVisible, split.aIndices);
  const piece = {
    ...cloneScene(node),
    id: newId("poly"),
    name: `${node.name.slice(0, 111)} tagliata`,
    points: split.bPoints.map(p => [...p]),
    ...(node.pointIds ? { pointIds: split.bIndices.map(index => node.pointIds[index]) } : {}),
    edgeVisible: cutVisibility(node.edgeVisible, split.bIndices),
  };
  target.siblings.splice(target.index + 1, 0, piece);
  return { scene: next, id: piece.id };
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
