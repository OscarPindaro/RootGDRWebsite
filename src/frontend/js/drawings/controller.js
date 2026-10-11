/* The drawing editor controller: tools, selection, transforms, styles, history
   and the explicit save.

   One controller owns one workspace. Interaction writes the in-memory document
   and re-renders; nothing is sent to the server until an explicit save, and a
   completed gesture is the unit of undo, never a pointer move. */

import {
  apply,
  distanceToSegment,
  invert,
  multiply,
  rotateAbout,
  scaleAbout,
  resizeFrame,
  translation,
} from "./geometry.js";
import {
  History,
  migrateScene,
  newId,
  addNode,
  createEllipse,
  createPath,
  createPolygon,
  createRect,
  createPreset,
  editPresetVertex,
  cutNode,
  duplicateNode,
  findNode,
  groupNodes,
  nodeAt,
  nodeBounds,
  nodeFrame,
  movePathPoint,
  pathCommands,
  pathPoints,
  patchNode,
  removeNode,
  reorderNode,
  reparentNode,
  setTransform,
  selectionCorners,
  transformInWorld,
  transformNodesInWorld,
  ungroupNode,
  validPolygon,
  visibilityIssues,
  worldPoints,
  walk,
  pathHandles,
} from "./scene.js";
import { render } from "./render.js";

const PALETTE = [
  "#ffffff", "#000000",
  "#d1402a", "#d97a26", "#e0a327", "#8a9a2b", "#3c7a52", "#1f7a7a",
  "#3f7fb0", "#2c46a8", "#4a3f8f", "#7b3f8f", "#c2506f", "#8a5a3c",
];

const SHAPE_NAMES = {
  triangle: "Triangolo",
  square: "Rettangolo",
  circle: "Cerchio",
  polygon: "Poligono",
  regular: "Poligono regolare",
  line: "Linea",
};

const PRESET_LABELS = {
  triangle_isosceles: "Isoscele", triangle_equilateral: "Equilatero",
  triangle_right_right: "Rettangolo · angolo a destra", triangle_right_left: "Rettangolo · angolo a sinistra",
  rectangle: "Rettangolo", square: "Quadrato", regular_polygon: "Poligono regolare", circle: "Cerchio", ellipse: "Ellisse",
};

function clamp(value, low, high) {
  return Math.max(low, Math.min(high, value));
}

/** Keep a scale factor's direction but bound its magnitude. */
function clampFactor(value) {
  const direction = value < 0 ? -1 : 1;
  return direction * clamp(Math.abs(value), 0.05, 20);
}

function round(value) {
  return Math.round(value * 1000) / 1000;
}

/** A stable serialization for the dirty check: object key order must not count.
    The server returns the document with its own field order and filled
    defaults, so a plain JSON.stringify would read as "changed" after a save. */
function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

export function createController(root) {
  const svg = root.querySelector("[data-drawing-artboard]");
  const sceneScript = root.querySelector("[data-drawing-scene]");
  const saveUrl = root.dataset.saveUrl || null;
  const contextMenu = root.querySelector("#drawing-context-menu");
  let contextPosition = null, contextOpener = svg;
  const editable = root.dataset.readonly !== "true" && !window.matchMedia("(max-width: 900px)").matches;

  let scene = migrateScene(sceneScript ? JSON.parse(sceneScript.textContent) : { schemaVersion: 2, artboard: { width: 640, height: 480, background: "#fffdf6" }, nodes: [] });
  const history = new History(scene);
  let selection = [];
  let selectedId = null;
  let tool = "select";
  let mode = "select";
  let creationPreset = null;
  let regularSides = 6;
  let pathPoint = null;
  let viewport = [1, 0, 0, 1, 0, 0];
  let drag = null;
  let pendingPolygon = null;
  let snapPoint = null;
  let snapGuides = [];
  let cut = null;
  let cutCursor = null;
  let spaceDown = false;
  const collapsed = new Set();
  let snapGrid = true;
  let snapShapes = true;
  let cutBefore = null;
  let gestureBefore = null;
  let title = root.dataset.title || "Nuovo disegno";
  let savedTitle = title;
  let allowLeave = false;

  let savedScene = canonical(scene);
  let savedVersion = Number(root.dataset.version || 0) || null;
  let inFlight = false;

  /* ---------- rendering ---------- */

  function view() {
    return {
      selection,
      selectedId,
      viewport,
      mode,
      pathPoint,
      tool,
      snap: snapPoint,
      guides: snapGuides,
      cut: cut && cutCursor ? { from: apply(nodeFrame(scene, cut.id).world, findNode(scene, cut.id).node.points[cut.index]), to: cutCursor } : null,
    };
  }

  function draw() {
    render(svg, scene, view());
    drawPending();
    renderLayers();
    syncControls();
    refresh();
  }

  /** The object list, rebuilt from the document: names, visibility, selection. */
  function renderLayers() {
    const list = root.querySelector("[data-testid='drawing-layers'] .drawing-editor__layers");
    if (!list) return;
    const focused = document.activeElement;
    const focusKey = focused && ["selectNode", "nodeCollapse", "nodeVisible"].find(key => focused.dataset?.[key]);
    const focusId = focusKey ? focused.dataset[focusKey] : null;
    const scroll = list.scrollTop;
    const build = (nodes, depth, inheritedHidden = false) => nodes.map(node => {
      const item = document.createElement("li");
      item.className = "drawing-editor__tree-node";
      item.setAttribute("role", "none");
      const row = document.createElement("div");
      row.className = "drawing-editor__layer" + (selection.includes(node.id) ? " is-selected" : "");
      row.dataset.nodeId = node.id;
      row.setAttribute("role", "treeitem");
      row.setAttribute("aria-level", String(depth + 1));
      row.setAttribute("aria-selected", String(selection.includes(node.id)));
      row.setAttribute("aria-label", node.name);
      if (inheritedHidden || !node.visible) row.classList.add("is-muted");
      if (node.kind === "group") {
        const branch = document.createElement("button");
        branch.type = "button";
        branch.className = "drawing-editor__branch";
        branch.dataset.nodeCollapse = node.id;
        branch.setAttribute("aria-label", `${collapsed.has(node.id) ? "Espandi" : "Comprimi"} ${node.name}`);
        row.setAttribute("aria-expanded", String(!collapsed.has(node.id)));
        branch.appendChild(root.querySelector("[data-scene-arrow]").content.cloneNode(true));
        if (collapsed.has(node.id)) branch.classList.add("is-collapsed");
        row.appendChild(branch);
      }
      const button = document.createElement("button");
      button.type = "button";
      button.className = "drawing-editor__layer-name";
      button.textContent = node.name;
      button.dataset.selectNode = node.id;
      button.dataset.testid = "drawing-layer";
      button.setAttribute("aria-pressed", String(selection.includes(node.id)));
      row.appendChild(button);
      const eye = document.createElement("button");
      eye.type = "button";
      eye.className = "drawing-editor__visibility";
      eye.dataset.nodeVisible = node.id;
      eye.disabled = !editable;
      eye.setAttribute("aria-pressed", String(node.visible));
      eye.setAttribute("aria-label", `${node.visible ? "Nascondi" : "Mostra"} ${node.name}`);
      eye.appendChild(root.querySelector(node.visible ? "[data-scene-eye]" : "[data-scene-eye-off]").content.cloneNode(true));
      row.appendChild(eye);
      item.appendChild(row);
      if (node.kind === "group") {
        const children = document.createElement("ul");
        children.className = "drawing-editor__children";
        children.setAttribute("role", "group");
        children.hidden = collapsed.has(node.id);
        children.append(...build(node.nodes, depth + 1, inheritedHidden || !node.visible));
        item.appendChild(children);
      }
      return item;
    });
    const rows = build(scene.nodes, 0);
    if (!rows.length) {
      const empty = document.createElement("li");
      empty.className = "drawing-editor__empty hint";
      empty.textContent = "Nessun oggetto";
      rows.push(empty);
    }
    list.replaceChildren(...rows);
    if (focusKey) ([...list.querySelectorAll("button")].find(button => button.dataset[focusKey] === focusId) || svg).focus({preventScroll:true});
    list.scrollTop = scroll;
  }

  /** The in-progress polygon: vertices already placed, still open. */
  function drawPending() {
    if (!pendingPolygon || !pendingPolygon.length) return;
    const overlay = svg.querySelector("[data-drawing-overlay]");
    const points = pendingPolygon
      .map((point) => apply(viewport, point))
      .map((point) => point.join(","))
      .join(" ");
    const poly = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
    poly.setAttribute("class", "drawing-editor__preview");
    poly.setAttribute("points", points);
    overlay.appendChild(poly);
  }

  function selected() {
    return selectedId ? findNode(scene, selectedId) : null;
  }

  /** Keep only the ids that still exist; the primary is the first survivor. */
  function pruneSelection() {
    selection = selection.filter((id) => Boolean(findNode(scene, id)));
    selectedId = selection.length ? selection[0] : null;
  }

  /** The ancestor ids of a node, outermost first. */
  function ancestorsOf(id, nodes = scene.nodes, chain = []) {
    for (const node of nodes) {
      if (node.id === id) return chain;
      if (node.kind === "group") {
        const nested = ancestorsOf(id, node.nodes, [...chain, node.id]);
        if (nested) return nested;
      }
    }
    return null;
  }

  /** A selected group that owns this node, if any: dragging inside it moves it. */
  function selectedAncestorOf(id) {
    return (ancestorsOf(id) || []).find((entry) => selection.includes(entry)) || null;
  }

  /* ---------- history ---------- */

  function commit(next) {
    history.commit(next);
    scene = history.present;
    pruneSelection();
    draw();
  }

  function undo() {
    if (!history.canUndo) return;
    scene = history.undo();
    pruneSelection();
    draw();
  }

  function redo() {
    if (!history.canRedo) return;
    scene = history.redo();
    pruneSelection();
    draw();
  }

  /* ---------- save ---------- */

  function status(message, state) {
    const output = document.querySelector("[data-autosave-status]");
    if (!output) return;
    output.textContent = message;
    output.hidden = !message;
    if (state) output.dataset.state = state;
    else delete output.dataset.state;
  }

  function announce(message) {
    const output = root.querySelector("[data-drawing-error]");
    if (!output) return;
    output.textContent = message;
    output.hidden = !message;
  }

  function errorMessage(code) {
    if (code === 401 || code === 403) return "Non hai i permessi per modificare questo disegno.";
    if (code === 404) return "Il disegno non esiste più.";
    if (code === 409) return "Il disegno è cambiato in un'altra scheda. Ricarica la pagina per vedere la versione più recente.";
    if (code === 422) return "Il disegno non è valido e non è stato salvato.";
    return "Non è stato possibile salvare. Riprova.";
  }

  function isDirty() {
    return canonical(scene) !== savedScene || title !== savedTitle;
  }

  function refresh() {
    root.dataset.dirty = isDirty() ? "true" : "false";
    if (root.dataset.saving === "true") return;
    status(isDirty() ? "Modifiche non salvate" : "Salvato", isDirty() ? "dirty" : "saved");
  }

  async function save(asCopy = false) {
    if (!saveUrl || inFlight) return;
    asCopy = asCopy === true;
    if (drag || cut) {
      announce("Completa o annulla l’operazione prima di salvare.");
      return;
    }
    inFlight = true;
    const lockedControls = asCopy ? [...root.querySelectorAll("input, button")].map(control => [control, control.disabled]) : [];
    root.dataset.copying = asCopy ? "true" : "";
    lockedControls.forEach(([control]) => { control.disabled = true; });
    root.dataset.saving = "true";
    status("Salvataggio…", "saving");
    announce("");
    let saved = false;
    try {
      const response = await fetch(asCopy ? "/api/drawings/" : saveUrl, {
        method: asCopy ? "POST" : "PATCH",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(asCopy ? { title: (title + " (copia)").slice(0, 255), scene } : { expectedVersion: savedVersion, title, scene }),
      });
      if (!response.ok) {
        root.querySelector("[data-drawing-conflict-actions]").hidden = response.status !== 409;
        announce(errorMessage(response.status));
        return;
      }
      const updated = await response.json();
      if (asCopy) {
        allowLeave = true;
        window.location.assign("/drawings/" + updated.id);
        return;
      }
      savedScene = canonical(updated.scene);
      savedTitle = updated.title || title;
      savedVersion = updated.version;
      root.querySelector("[data-drawing-conflict-actions]").hidden = true;
      saved = true;
    } catch (error) {
      announce("Rete non raggiungibile. Il disegno non è stato salvato.");
    } finally {
      inFlight = false;
      delete root.dataset.copying;
      lockedControls.forEach(([control, disabled]) => { control.disabled = disabled; });
      delete root.dataset.saving;
      if (saved) refresh();
      else status("Non salvato", "error");
    }
  }

  /* ---------- coordinates ---------- */

  function artboardPoint(event) {
    const ctm = svg.getScreenCTM();
    if (!ctm) return [0, 0];
    const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(ctm.inverse());
    return [point.x, point.y];
  }

  function scenePoint(event) {
    return apply(invert(viewport), artboardPoint(event));
  }

  function worldCorners(node) {
    return selectionCorners(scene, [node.id]);
  }

  /* ---------- snapping ---------- */

  const SNAP_TOLERANCE_PX = 8;
  const SNAP_GRID = 10;

  /** Snap a world point to the grid or a sibling vertex; Alt bypasses it. */
  function snapWorld(point, node, excludeIndex, bypass, excluded = []) {
    if (bypass) return { point, snapped: false, guides: [] };
    const tolerance = SNAP_TOLERANCE_PX / (viewport[0] * Math.hypot(svg.getScreenCTM().a, svg.getScreenCTM().b));
    let best = null, bestDistance = tolerance;
    const alignments = [null, null], distances = [tolerance, tolerance];
    walk(scene.nodes, candidate => {
      if (!snapShapes || excluded.includes(candidate.id) || candidate.visible === false || candidate.opacity === 0 || (ancestorsOf(candidate.id) || []).some(id => excluded.includes(id) || !findNode(scene, id).node.visible)) return;
      const points = candidate.kind === "polygon" ? candidate.points : candidate.kind === "path" ? pathHandles(candidate.d).filter(h => !h.control).map(h => h.point) : candidate.kind === "ellipse" ? [[candidate.cx, candidate.cy], [candidate.cx + candidate.rx, candidate.cy], [candidate.cx - candidate.rx, candidate.cy], [candidate.cx, candidate.cy + candidate.ry], [candidate.cx, candidate.cy - candidate.ry]] : [];
      const world = nodeFrame(scene, candidate.id).world;
      const targets = points.filter((p, i) => candidate.id !== node?.id || i !== excludeIndex);
      if (candidate.kind === "polygon") targets.push(...points.map((p, i) => [(p[0] + points[(i + 1) % points.length][0]) / 2, (p[1] + points[(i + 1) % points.length][1]) / 2]));
      targets.forEach(local => {
        const vertex = apply(world, local), distance = Math.hypot(vertex[0] - point[0], vertex[1] - point[1]);
        if (distance < bestDistance) { bestDistance = distance; best = vertex; }
      });
      if (candidate.id === node?.id || (candidate.kind === "group" && !candidate.nodes.length)) return;
      const corners = worldCorners(candidate);
      for (let axis = 0; axis < 2; axis += 1) {
        const low = Math.min(...corners.map(corner => corner[axis])), high = Math.max(...corners.map(corner => corner[axis]));
        for (const value of [low, (low + high) / 2, high]) {
          const distance = Math.abs(value - point[axis]);
          if (distance < distances[axis]) { distances[axis] = distance; alignments[axis] = value; }
        }
      }
    });
    const grid = point.map(value => Math.round(value / SNAP_GRID) * SNAP_GRID);
    if (snapGrid && Math.hypot(grid[0] - point[0], grid[1] - point[1]) < bestDistance) best = grid;
    const result = best ? [...best] : [...point];
    const guides = best ? [{axis:0, value:best[0]}, {axis:1, value:best[1]}] : [];
    for (let axis = 0; axis < 2; axis += 1) {
      if (alignments[axis] !== null && (!best || distances[axis] < Math.abs(result[axis] - point[axis]))) {
        result[axis] = alignments[axis];
        const previous = guides.find(guide => guide.axis === axis);
        if (previous) previous.value = result[axis];
        else guides.push({axis, value:result[axis]});
      }
    }
    return { point:result, snapped:guides.length > 0, guides };
  }

  function snapFeedback(snapped, actual = snapped.point) {
    snapPoint = snapped.snapped && Math.hypot(actual[0] - snapped.point[0], actual[1] - snapped.point[1]) < 0.001 ? actual : null;
    snapGuides = snapped.guides.filter(guide => Math.abs(actual[guide.axis] - guide.value) < 0.001);
  }

  /* ---------- vertex editing ---------- */

  function edgeVisibility(node) {
    return node.edgeVisible ? [...node.edgeVisible] : node.points.map(() => true);
  }

  function insertVertex(edgeIndex, localPoint) {
    const node = selected().node;
    if (node.constraint) { announce("Sblocca la forma prima di aggiungere vertici."); return; }
    const points = node.points.map((point) => [...point]);
    points.splice(edgeIndex + 1, 0, [round(localPoint[0]), round(localPoint[1])]);
    if (!validPolygon(points)) return;
    const pointIds = [...node.pointIds];
    pointIds.splice(edgeIndex + 1, 0, newId("v"));
    const patch = { points, pointIds };
    if (node.edgeVisible) {
      const visible = edgeVisibility(node);
      // The split edge keeps its own visibility on both halves.
      visible.splice(edgeIndex + 1, 0, visible[edgeIndex]);
      patch.edgeVisible = visible;
    }
    commit(patchNode(scene, selectedId, patch));
  }

  function removeVertex(index) {
    const node = selected().node;
    if (node.constraint) { announce("Sblocca la forma prima di rimuovere vertici."); return; }
    if (node.points.length <= 3) {
      announce("Un poligono ha almeno tre vertici.");
      return;
    }
    const points = node.points.filter((_, position) => position !== index);
    if (!validPolygon(points)) {
      announce("Il poligono perderebbe la sua area.");
      return;
    }
    const patch = { points, pointIds: node.pointIds.filter((_, position) => position !== index) };
    if (node.edgeVisible) {
      patch.edgeVisible = edgeVisibility(node).filter((_, position) => position !== index);
    }
    announce("");
    commit(patchNode(scene, selectedId, patch));
  }

  /** The nearest polygon edge to a local point, with the projection onto it. */
  function closestEdge(node, localPoint, tolerance) {
    let best = null;
    let bestDistance = tolerance;
    for (let index = 0; index < node.points.length; index += 1) {
      const a = node.points[index];
      const b = node.points[(index + 1) % node.points.length];
      const distance = distanceToSegment(localPoint, a, b);
      if (distance <= bestDistance) {
        bestDistance = distance;
        const dx = b[0] - a[0];
        const dy = b[1] - a[1];
        const lengthSquared = dx * dx + dy * dy || 1;
        let t = ((localPoint[0] - a[0]) * dx + (localPoint[1] - a[1]) * dy) / lengthSquared;
        t = Math.max(0, Math.min(1, t));
        best = { edge: index, point: [a[0] + t * dx, a[1] + t * dy] };
      }
    }
    return best;
  }

  function toggleEdge(index) {
    const node = selected().node;
    const visible = edgeVisibility(node);
    visible[index] = !visible[index];
    commit(patchNode(scene, selectedId, { edgeVisible: visible }));
  }

  /* ---------- straight cut ---------- */

  const VERTEX_TOLERANCE_PX = 9;

  /** Where on the polygon boundary a click landed: a vertex, or a new point. */
  function boundaryAt(node, world) {
    const inverse = invert(nodeFrame(scene, node.id).world);
    if (!inverse) return null;
    const local = apply(inverse, world);
    const vertexTolerance = VERTEX_TOLERANCE_PX / viewport[0];
    for (let index = 0; index < node.points.length; index += 1) {
      const point = node.points[index];
      if (Math.hypot(point[0] - local[0], point[1] - local[1]) <= vertexTolerance) {
        return { index, insert: false };
      }
    }
    const hit = closestEdge(node, local, SNAP_TOLERANCE_PX / viewport[0]);
    return hit ? { index: hit.edge + 1, point: hit.point, insert: true } : null;
  }

  /** A cut needs its endpoints to be vertices: insert one on the edge clicked. */
  function ensureVertex(nodeId, boundary) {
    if (!boundary.insert) return boundary.index;
    const node = findNode(scene, nodeId).node;
    const points = node.points.map((point) => [...point]);
    points.splice(boundary.index, 0, [round(boundary.point[0]), round(boundary.point[1])]);
    const pointIds = [...node.pointIds];
    pointIds.splice(boundary.index, 0, newId("v"));
    const patch = { points, pointIds };
    if (node.edgeVisible) {
      const visible = edgeVisibility(node);
      visible.splice(boundary.index, 0, visible[boundary.index - 1] !== false);
      patch.edgeVisible = visible;
    }
    // Uncommitted: the whole cut is one history step.
    scene = patchNode(scene, nodeId, patch);
    return boundary.index;
  }

  function cutClick(event) {
    const world = scenePoint(event);
    const hit = selectedId ? selected().node : nodeAt(scene, world);
    if (!hit) return;
    if (hit.kind !== "polygon") {
      announce("Il taglio funziona sui poligoni.");
      return;
    }
    if (selectedId !== hit.id) {
      selectedId = hit.id;
      cut = null;
    }
    const boundary = boundaryAt(hit, world);
    if (!boundary) {
      announce("Clicca sul bordo del poligono per scegliere i due punti.");
      return;
    }
    if (!cutBefore) cutBefore = scene;
    const index = ensureVertex(hit.id, boundary);
    if (cut && boundary.insert && index <= cut.index) cut.index += 1;
    if (!cut) {
      cut = { id: hit.id, index };
      cutCursor = world;
      draw();
      return;
    }
    const result = cutNode(scene, cut.id, cut.index, index);
    cut = null;
    cutCursor = null;
    if (!result) {
      scene = cutBefore;
      cutBefore = null;
      announce("Il taglio non è valido: serve una corda interna fra due vertici non adiacenti.");
      draw();
      return;
    }
    announce("");
    cutBefore = null;
    commit(result.scene);
    // The selection stays on the piece that kept the original id, so the cut
    // does not move the user's selection: the tip they were editing is still
    // the selected shape and can be recoloured straight away.
    setSelection([hit.id]);
    draw();
  }

  /* ---------- tools ---------- */

  function setTool(next) {
    if (cutBefore) scene = cutBefore;
    cutBefore = null;
    tool = next;
    pendingPolygon = null;
    cut = null;
    cutCursor = null;
    snapPoint = null;
    snapGuides = [];
    // Vertex handles belong to the select tool; a tool switch leaves that mode.
    mode = next === "select" ? defaultMode() : "select";
    root.querySelectorAll("[data-tool]").forEach((button) => {
      const active = button.dataset.tool === next || (next === "regular" && button.dataset.tool === "polygon");
      button.classList.toggle("is-selected", active);
      button.setAttribute("aria-pressed", String(active));
    });
    draw();
  }

  function defaultMode() {
    if (!selection.length) return "select";
    return selection.length === 1 && selected()?.node.kind !== "group" ? "vertex" : "transform";
  }

  function setMode(next) {
    if (tool !== "select") setTool("select");
    mode = next;
    draw();
  }

  function select(id, additive = false) {
    pathPoint = null;
    if (!id) {
      selection = [];
    } else if (additive) {
      selection = selection.includes(id)
        ? selection.filter((entry) => entry !== id)
        : [...selection, id];
    } else {
      selection = [id];
    }
    selection = selection.filter(id => !(ancestorsOf(id) || []).some(parent => selection.includes(parent)));
    selectedId = selection.length ? selection[0] : null;
    mode = defaultMode();
    draw();
  }

  /** Select exactly these ids; used by the actions that produce new shapes. */
  function setSelection(ids) {
    selection = ids.filter((id) => Boolean(findNode(scene, id)));
    selectedId = selection.length ? selection[0] : null;
  }

  function beginShape(event) {
    const snapped = snapWorld(scenePoint(event), null, -1, event.altKey);
    snapFeedback(snapped);
    drag = { kind: "create", tool, preset: creationPreset, sides: regularSides, from: snapped.point, to: snapped.point };
    previewDrag();
  }

  function finishShape() {
    if (!drag) return;
    const { tool: shape, preset, sides, from, to } = drag;
    drag = null;
    const minX = Math.min(from[0], to[0]);
    const maxX = Math.max(from[0], to[0]);
    const minY = Math.min(from[1], to[1]);
    const maxY = Math.max(from[1], to[1]);
    if (maxX - minX < 4 || maxY - minY < 4) return;
    const name = SHAPE_NAMES[shape] || "Forma";
    let node = null;
    if (preset) {
      node = createPreset(preset, [minX, minY], [maxX, maxY], sides);
    } else if (shape === "circle") {
      node = createEllipse(name, [(minX + maxX) / 2, (minY + maxY) / 2], (maxX - minX) / 2, (maxY - minY) / 2);
    }
    if (!node) return;
    commit(addNode(scene, node));
    setSelection([node.id]);
    setTool("select");
  }

  function beginLine(event) {
    const snapped = snapWorld(scenePoint(event), null, -1, event.altKey);
    snapFeedback(snapped);
    drag = { kind: "line", curve: tool === "curve", from: snapped.point, to: snapped.point };
    previewDrag();
  }

  function finishLine() {
    if (!drag) return;
    const { from, to, curve } = drag;
    drag = null;
    const length = Math.hypot(to[0] - from[0], to[1] - from[1]);
    if (length < 4) return;
    // A curve bulges to one side of the drag: control points at a quarter and
    // three quarters, offset perpendicular by a third of the length.
    const normal = [-(to[1] - from[1]) / length, (to[0] - from[0]) / length];
    const bulge = length / 3;
    const d = curve
      ? `M${round(from[0])} ${round(from[1])} ` +
        `C${round(from[0] + (to[0] - from[0]) * 0.25 + normal[0] * bulge)} ${round(from[1] + (to[1] - from[1]) * 0.25 + normal[1] * bulge)} ` +
        `${round(from[0] + (to[0] - from[0]) * 0.75 + normal[0] * bulge)} ${round(from[1] + (to[1] - from[1]) * 0.75 + normal[1] * bulge)} ` +
        `${round(to[0])} ${round(to[1])}`
      : `M${round(from[0])} ${round(from[1])} L${round(to[0])} ${round(to[1])}`;
    const node = createPath(curve ? "Curva" : "Linea", d);
    node.fill = null;
    commit(addNode(scene, node));
    setSelection([node.id]);
    setTool("select");
  }

  function addPolygonPoint(event) {
    const snapped = snapWorld(scenePoint(event), null, -1, event.altKey);
    snapFeedback(snapped);
    const point = snapped.point;
    if (!pendingPolygon) pendingPolygon = [];
    pendingPolygon.push([round(point[0]), round(point[1])]);
    draw();
  }

  function finishPolygon() {
    if (!pendingPolygon || pendingPolygon.length < 3) return;
    if (!validPolygon(pendingPolygon)) {
      announce("Il poligono si interseca o non ha area: correggi i punti prima di chiuderlo.");
      return;
    }
    const node = createPolygon("Poligono", pendingPolygon);
    pendingPolygon = null;
    announce("");
    commit(addNode(scene, node));
    setSelection([node.id]);
    setTool("select");
  }

  function cancelPolygon() {
    pendingPolygon = null;
    announce("");
    draw();
  }

  /* ---------- pointer ---------- */

  function onPointerDown(event) {
    if (!editable || root.dataset.copying || ![0, 1].includes(event.button)) return;
    event.preventDefault();
    svg.focus({ preventScroll: true });
    svg.setPointerCapture(event.pointerId);
    gestureBefore = scene;
    const target = event.target;
    // Pan with the middle button or with Space held: Shift belongs to
    // multi-selection, not to panning.
    if (event.button === 1 || (event.button === 0 && spaceDown)) {
      drag = { kind: "pan", from: artboardPoint(event), pan: [viewport[4], viewport[5]] };
      return;
    }
    if (event.button !== 0) return;
    if (target.dataset.pathCommand !== undefined && mode === "vertex" && selectedId) {
      pathPoint = `${target.dataset.pathCommand}:${target.dataset.pathOffset}`;
      const node = selected().node;
      drag = { kind: "path", id: selectedId, command: Number(target.dataset.pathCommand), offset: Number(target.dataset.pathOffset), d: node.d, transform: nodeFrame(scene, selectedId).world };
      return;
    }

    if (target.dataset.vertex !== undefined && mode === "vertex" && selectedId) {
      const node = selected().node;
      if (event.altKey) {
        removeVertex(Number(target.dataset.vertex));
        return;
      }
      drag = { kind: "vertex", id: selectedId, index: Number(target.dataset.vertex), node, transform: nodeFrame(scene, selectedId).world, points: node.points.map((point) => [...point]) };
      return;
    }
    if (target.dataset.edge !== undefined && mode === "vertex" && selectedId) {
      toggleEdge(Number(target.dataset.edge));
      return;
    }
    if (target.dataset.ellipseAxis && mode === "vertex" && selectedId) {
      drag = { kind: "ellipse", id: selectedId, axis: target.dataset.ellipseAxis, node: selected().node, transform: nodeFrame(scene, selectedId).world };
      return;
    }
    if (mode === "vertex" && selectedId && tool === "select") {
      const node = selected().node;
      const local = apply(invert(nodeFrame(scene, selectedId).world), scenePoint(event));
      if (node.kind === "polygon" && closestEdge(node, local, SNAP_TOLERANCE_PX / viewport[0])) return;
      if (node.kind === "path") {
        const points = pathPoints(node.d);
        if (points.slice(1).some((point, index) => distanceToSegment(local, points[index], point) < SNAP_TOLERANCE_PX / viewport[0])) return;
      }
    }
    // The transform handles belong to the select tool; another tool's clicks
    // must reach the canvas, not a handle sitting on the same corner.
    if (target.dataset.corner !== undefined && selectedId && tool === "select") {
      const node = selected().node;
      drag = { kind: "scale", corner: Number(target.dataset.corner), transforms: selection.map(id => ({ id, transform: nodeFrame(scene, id).world })), corners: selectionCorners(scene, selection), from: scenePoint(event) };
      return;
    }
    if (target.classList.contains("drawing-editor__rotate-handle") && selectedId && tool === "select") {
      const node = selected().node;
      const corners = selectionCorners(scene, selection);
      const center = [(corners[0][0] + corners[2][0]) / 2, (corners[0][1] + corners[2][1]) / 2];
      drag = { kind: "rotate", transforms: selection.map(id => ({ id, transform: nodeFrame(scene, id).world })), center, start: Math.atan2(scenePoint(event)[1] - center[1], scenePoint(event)[0] - center[0]) };
      return;
    }

    if (tool === "polygon") return;
    if (tool === "cut") {
      cutClick(event);
      return;
    }
    if (tool === "line" || tool === "curve") {
      beginLine(event);
      return;
    }
    if (tool !== "select") {
      beginShape(event);
      return;
    }

    const hit = nodeAt(scene, scenePoint(event));
    if (!hit) {
      select(null);
      return;
    }
    // A click inside a selected group moves the group, not the child under it.
    const owner = selectedAncestorOf(hit.id);
    if (!owner && event.shiftKey) {
      select(hit.id, true);
      return;
    }
    if (!owner && !selection.includes(hit.id)) select(hit.id);
    drag = {
      kind: "move",
      from: scenePoint(event),
      anchor: worldCorners(selected().node)[0],
      transforms: selection.map((id) => ({ id, transform: nodeFrame(scene, id).world })),
    };
  }

  function onPointerMove(event) {
    if (tool === "cut" && cut) {
      cutCursor = scenePoint(event);
      draw();
      return;
    }
    if (!drag) return;
    if (drag.kind === "pan") {
      const point = artboardPoint(event);
      viewport = [...viewport.slice(0, 4), drag.pan[0] + (point[0] - drag.from[0]), drag.pan[1] + (point[1] - drag.from[1])];
      draw();
      return;
    }
    if (drag.kind === "create" || drag.kind === "line") {
      const snapped = snapWorld(scenePoint(event), null, -1, event.altKey);
      snapFeedback(snapped);
      drag.to = snapped.point;
      previewDrag();
      return;
    }
    if (drag.kind === "move") {
      const point = scenePoint(event);
      const wanted = [drag.anchor[0] + point[0] - drag.from[0], drag.anchor[1] + point[1] - drag.from[1]];
      const snapped = snapWorld(wanted, null, -1, event.altKey, selection);
      snapFeedback(snapped);
      const delta = translation(snapped.point[0] - drag.anchor[0], snapped.point[1] - drag.anchor[1]);
      let next = scene;
      for (const entry of drag.transforms) {
        next = transformInWorld(next, entry.id, delta, entry.transform);
      }
      scene = next;
      draw();
      return;
    }
    if (drag.kind === "scale") {
      const snapped = snapWorld(scenePoint(event), null, -1, event.altKey, selection);
      const frame = resizeFrame(drag.corners, drag.corner, snapped.point);
      if (!frame) return;
      let {sx, sy} = frame, uniform = event.shiftKey;
      walk(scene.nodes, node => {
        if (["circle", "square", "triangle_equilateral", "regular_polygon"].includes(node.constraint?.kind) && (selection.includes(node.id) || (ancestorsOf(node.id) || []).some(id => selection.includes(id)))) uniform = true;
      });
      if (uniform) {
        const magnitude = Math.max(Math.abs(sx), Math.abs(sy));
        sx = (sx < 0 ? -1 : 1) * magnitude;
        sy = (sy < 0 ? -1 : 1) * magnitude;
      }
      const delta = multiply(frame.basis, multiply([clampFactor(sx), 0, 0, clampFactor(sy), 0, 0], frame.inverse));
      const next = transformNodesInWorld(scene, drag.transforms, delta), rejected = next === scene;
      if (rejected) announce("Trasformazione incompatibile con i vincoli: sblocca la geometria per deformarla.");
      else { announce(""); scene = next; }
      snapFeedback(rejected ? {...snapped, snapped:false, guides:[]} : snapped, apply(delta, drag.corners[drag.corner]));
      draw();
      return;
    }
    if (drag.kind === "rotate") {
      const point = scenePoint(event);
      const angle = Math.atan2(point[1] - drag.center[1], point[0] - drag.center[0]) - drag.start;
      const delta = rotateAbout(drag.center, angle);
      const next = transformNodesInWorld(scene, drag.transforms, delta);
      if (next === scene) announce("Trasformazione incompatibile con i vincoli: sblocca la geometria per deformarla.");
      else { announce(""); scene = next; }
      draw();
      return;
    }
    if (drag.kind === "path") {
      const snapped = snapWorld(scenePoint(event), null, -1, event.altKey, selection);
      const local = apply(invert(drag.transform), snapped.point);
      snapFeedback(snapped);
      scene = patchNode(scene, drag.id, { d: movePathPoint(drag.d, drag.command, drag.offset, local) });
      draw();
      return;
    }
    if (drag.kind === "ellipse") {
      const snapped = snapWorld(scenePoint(event), null, -1, event.altKey, selection);
      snapFeedback(snapped);
      const local = apply(invert(drag.transform), snapped.point);
      const radius = clamp(Math.hypot(local[0] - drag.node.cx, local[1] - drag.node.cy), 0.1, 100000);
      const patch = drag.axis === "center" ? { cx: round(local[0]), cy: round(local[1]) }
        : drag.node.constraint?.kind === "circle" ? { rx: radius, ry: radius }
        : drag.axis === "x" ? { rx: clamp(Math.abs(local[0] - drag.node.cx), 0.1, 100000) }
        : { ry: clamp(Math.abs(local[1] - drag.node.cy), 0.1, 100000) };
      scene = patchNode(scene, drag.id, patch);
      draw();
      return;
    }
    if (drag.kind === "vertex") {
      const inverse = invert(drag.transform);
      if (!inverse) return;
      const snapped = snapWorld(scenePoint(event), drag.node, drag.index, event.altKey);
      snapFeedback(snapped);
      const local = apply(inverse, snapped.point);
      const points = editPresetVertex(drag.node, drag.index, [round(local[0]), round(local[1])]);
      if (!validPolygon(points)) return;
      scene = patchNode(scene, drag.id, { points });
      snapFeedback(snapped, apply(drag.transform, findNode(scene, drag.id).node.points[drag.index]));
      draw();
    }
  }

  function onPointerUp() {
    if (!drag) return;
    const finished = drag;
    snapPoint = null;
    snapGuides = [];
    if (finished.kind === "create") finishShape();
    else if (finished.kind === "line") finishLine();
    else if (finished.kind === "move" || finished.kind === "scale" || finished.kind === "rotate" || finished.kind === "vertex" || finished.kind === "path" || finished.kind === "ellipse") {
      drag = null;
      commit(scene);
    } else {
      drag = null;
    }
    draw();
  }

  /** A live outline while a shape or line is being dragged. */
  function previewDrag() {
    draw();
    if (!drag || !drag.to) return;
    const overlay = svg.querySelector("[data-drawing-overlay]");
    const from = apply(viewport, drag.from);
    const to = apply(viewport, drag.to);
    const line = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
    line.setAttribute("class", "drawing-editor__preview");
    line.setAttribute("points", `${from[0]},${from[1]} ${to[0]},${to[1]}`);
    overlay.appendChild(line);
    if (drag.kind === "create") {
      const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      rect.setAttribute("class", "drawing-editor__preview");
      rect.setAttribute("x", Math.min(from[0], to[0]));
      rect.setAttribute("y", Math.min(from[1], to[1]));
      rect.setAttribute("width", Math.abs(to[0] - from[0]));
      rect.setAttribute("height", Math.abs(to[1] - from[1]));
      overlay.appendChild(rect);
    }
  }

  function onWheel(event) {
    if (!editable) return;
    event.preventDefault();
    const point = artboardPoint(event);
    const factor = event.deltaY < 0 ? 1.1 : 1 / 1.1;
    const next = clamp(viewport[0] * factor, 0.1, 8);
    const scale = next / viewport[0];
    viewport = [next, 0, 0, next, point[0] - scale * (point[0] - viewport[4]), point[1] - scale * (point[1] - viewport[5])];
    draw();
  }

  /* ---------- keyboard ---------- */

  function positionContext() {
    if (!contextPosition || !contextMenu.matches(":popover-open")) return;
    const [x, y] = contextPosition;
    contextMenu.style.left = Math.max(8, Math.min(x, window.innerWidth - contextMenu.offsetWidth - 8)) + "px";
    contextMenu.style.top = Math.max(8, Math.min(y, window.innerHeight - contextMenu.offsetHeight - 8)) + "px";
  }

  function openContext(position = null) {
    if (!editable || root.dataset.copying || drag || cut) return false;
    contextOpener = root.contains(document.activeElement) ? document.activeElement : svg;
    contextPosition = position;
    syncControls();
    contextMenu.showPopover();
    positionContext();
    return true;
  }

  function onKeyDown(event) {
    if (!editable || event.defaultPrevented || root.dataset.copying || !root.isConnected || !root.contains(document.activeElement) || document.querySelector("dialog[open]") || root.querySelector("[data-menu]:popover-open")) return;
    const mod = event.ctrlKey || event.metaKey;
    if (mod && event.key.toLowerCase() === "s") {
      event.preventDefault();
      execute("save");
      return;
    }
    if (event.target.closest("input, textarea, select, [contenteditable]:not([contenteditable='false'])")) return;
    if (mode === "vertex" && event.target.dataset.ellipseAxis && selectedId && ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) {
      event.preventDefault();
      const axis = event.target.dataset.ellipseAxis, node = selected().node;
      const field = axis === "center" ? (["ArrowLeft", "ArrowRight"].includes(event.key) ? "cx" : "cy") : axis === "x" ? "rx" : "ry";
      const step = (event.shiftKey ? 10 : 1) * (["ArrowLeft", "ArrowUp"].includes(event.key) ? -1 : 1);
      execute("ellipse-parameter", {field, value:node[field] + step});
      svg.querySelector(`[data-ellipse-axis='${axis}']`)?.focus();
      return;
    }
    if (mode === "vertex" && event.target.dataset.pathCommand !== undefined && selectedId) {
      const nudges = {ArrowLeft:[-1,0], ArrowRight:[1,0], ArrowUp:[0,-1], ArrowDown:[0,1]};
      if (nudges[event.key]) {
        event.preventDefault();
        const command = Number(event.target.dataset.pathCommand);
        const offset = Number(event.target.dataset.pathOffset);
        const node = selected().node;
        const frame = nodeFrame(scene, selectedId).world;
        const point = pathCommands(node.d)[command].numbers.slice(offset, offset + 2);
        const world = apply(frame, point);
        const step = event.shiftKey ? 10 : 1;
        const [dx, dy] = nudges[event.key];
        const next = apply(invert(frame), [world[0] + dx * step, world[1] + dy * step]);
        pathPoint = `${command}:${offset}`;
        commit(patchNode(scene, selectedId, {d:movePathPoint(node.d, command, offset, next)}));
        svg.querySelector(`[data-path-command='${command}'][data-path-offset='${offset}']`)?.focus();
        return;
      }
    }
    if (!mod && !event.altKey && event.key === "/") {
      if (openContext()) event.preventDefault();
      return;
    }
    if (!mod && !event.altKey && event.key.toLowerCase() === "t" && canExecute("transform")) {
      event.preventDefault();
      execute("transform");
      return;
    }
    if (mod && event.key.toLowerCase() === "z" && !event.shiftKey) {
      event.preventDefault();
      execute("undo");
      return;
    }
    if (mod && (event.key.toLowerCase() === "y" || (event.key.toLowerCase() === "z" && event.shiftKey))) {
      event.preventDefault();
      execute("redo");
      return;
    }
    if (event.key === "Enter" && pendingPolygon) {
      event.preventDefault();
      finishPolygon();
      return;
    }
    if (event.key === "Escape" && pendingPolygon) {
      event.preventDefault();
      cancelPolygon();
      return;
    }
    if (event.key === "Escape" && drag) {
      event.preventDefault();
      scene = gestureBefore;
      drag = null;
      snapPoint = null;
      snapGuides = [];
      draw();
      return;
    }
    if (event.key === "Escape" && cut) {
      event.preventDefault();
      if (cutBefore) scene = cutBefore;
      cutBefore = null;
      cut = null;
      cutCursor = null;
      announce("");
      draw();
      return;
    }
    if (event.key === "Escape") {
      select(null);
      return;
    }
    if (!selectedId) return;
    if (event.key === "Delete" || event.key === "Backspace") {
      event.preventDefault();
      execute("delete");
      return;
    }
    if (mod && event.key.toLowerCase() === "d") {
      event.preventDefault();
      execute("duplicate");
      return;
    }
    const nudge = event.shiftKey ? 10 : 1;
    const steps = { ArrowLeft: [-nudge, 0], ArrowRight: [nudge, 0], ArrowUp: [0, -nudge], ArrowDown: [0, nudge] };
    if (steps[event.key] && (event.target === svg || event.target === root)) {
      event.preventDefault();
      const [dx, dy] = steps[event.key];
      let next = scene;
      for (const id of selection) next = transformInWorld(next, id, translation(dx, dy));
      commit(next);
    }
  }

  /* ---------- actions ---------- */

  function deleteSelected() {
    if (!selection.length) return;
    let next = scene;
    for (const id of selection) next = removeNode(next, id);
    selection = [];
    selectedId = null;
    commit(next);
    draw();
  }

  function duplicateSelected() {
    if (!selection.length) return;
    let next = scene;
    const copies = [];
    for (const id of selection) {
      const result = duplicateNode(next, id);
      next = result.scene;
      copies.push(result.id);
    }
    commit(next);
    selection = copies;
    selectedId = copies[0] || null;
    draw();
  }

  function groupSelected() {
    if (selection.length < 2) {
      announce("Seleziona almeno due oggetti per raggrupparli.");
      return;
    }
    const result = groupNodes(scene, selection);
    if (!result) {
      announce("Il gruppo non è valido: gli oggetti devono essere allo stesso livello e non troppo annidati.");
      return;
    }
    announce("");
    commit(result.scene);
    selection = [result.id];
    selectedId = result.id;
    draw();
  }

  function ungroupSelected() {
    if (!selectedId) return;
    const result = ungroupNode(scene, selectedId);
    if (!result) {
      announce("Seleziona un gruppo per separarlo.");
      return;
    }
    announce("");
    commit(result.scene);
    selection = result.ids;
    selectedId = result.ids[0] || null;
    draw();
  }

  function renameSelected(name) {
    if (!selectedId) return;
    const trimmed = name.trim();
    if (!trimmed) return;
    commit(patchNode(scene, selectedId, { name: trimmed }));
  }

  function applyStyle(patch) {
    if (!selectedId) return;
    commit(patchNode(scene, selectedId, patch));
  }

  function setEllipseParameter({field, value} = {}) {
    if (!["cx", "cy", "rx", "ry"].includes(field) || !Number.isFinite(value) || Math.abs(value) > 100000 || (["rx", "ry"].includes(field) && value <= 0)) {
      announce("Usa valori finiti entro 100000 unità e raggi maggiori di zero.");
      syncControls();
      return false;
    }
    const node = selected().node;
    const patch = node.constraint?.kind === "circle" && ["rx", "ry"].includes(field) ? {rx:value, ry:value} : {[field]:value};
    const next = patchNode(scene, selectedId, patch);
    if (next === scene) announce("Il valore non rispetta i vincoli della forma.");
    else { announce(""); commit(next); }
  }

  const actions = {
    select: { label: "Seleziona", enabled: () => true, run: () => setMode("select") },
    edit: { label: "Modifica forma", enabled: () => selection.length === 1 && selected()?.node.kind !== "group", run: () => setMode("vertex") },
    transform: { label: "Trasforma", enabled: () => selection.length > 0, run: () => setMode("transform") },
    undo: { label: "Annulla", enabled: () => history.canUndo, run: undo },
    redo: { label: "Ripeti", enabled: () => history.canRedo, run: redo },
    save: { label: "Salva", enabled: () => Boolean(saveUrl) && !inFlight, run: save },
    delete: { label: "Elimina", enabled: () => selection.length > 0, run: deleteSelected },
    duplicate: { label: "Duplica", enabled: () => selection.length > 0, run: duplicateSelected },
    group: { label: "Raggruppa", enabled: () => selection.length > 1 && Boolean(groupNodes(scene, selection)), run: groupSelected },
    ungroup: { label: "Separa", enabled: () => selection.length === 1 && selected()?.node.kind === "group", run: ungroupSelected },
    forward: { label: "Porta avanti", enabled: () => selection.length === 1 && selected().index < selected().siblings.length - 1, run: () => commit(reorderNode(scene, selectedId, 1)) },
    backward: { label: "Porta indietro", enabled: () => selection.length === 1 && selected().index > 0, run: () => commit(reorderNode(scene, selectedId, -1)) },
    front: { label: "Primo piano", enabled: () => selection.length === 1 && selected().index < selected().siblings.length - 1, run: () => commit(reorderNode(scene, selectedId, selected().siblings.length)) },
    back: { label: "Sfondo", enabled: () => selection.length === 1 && selected().index > 0, run: () => commit(reorderNode(scene, selectedId, -selected().siblings.length)) },
    unlock: { label: "Sblocca geometria", enabled: () => selection.length === 1 && Boolean(selected()?.node.constraint), run: () => commit(patchNode(scene, selectedId, { constraint: null })) },
    "ellipse-parameter": { label: "Modifica centro e raggi", enabled: () => selection.length === 1 && selected()?.node.kind === "ellipse", run: setEllipseParameter },
  };

  for (const name of [...Object.keys(SHAPE_NAMES), "curve", "cut"]) {
    actions[`tool-${name}`] = { label: SHAPE_NAMES[name] || (name === "curve" ? "Curva" : "Taglia"), enabled: () => name !== "cut" || (selection.length === 1 && selected()?.node.kind === "polygon" && !selected().node.constraint), run: () => {
      creationPreset = {triangle:"triangle_isosceles", square:"rectangle", regular:"regular_polygon", circle:"circle"}[name] || null;
      setTool(name);
    } };
  }
  for (const [kind, label] of Object.entries(PRESET_LABELS)) {
    actions[`preset-${kind}`] = { label, enabled: () => true, run: () => {
      creationPreset = kind;
      setTool(kind.startsWith("triangle_") ? "triangle" : ["square", "rectangle"].includes(kind) ? "square" : ["circle", "ellipse"].includes(kind) ? "circle" : "regular");
    } };
  }

  function canExecute(id) {
    return Boolean(editable && !root.dataset.copying && !drag && !cut && actions[id]?.enabled());
  }

  function execute(id, parameters) {
    if (!canExecute(id)) return false;
    return actions[id].run(parameters) !== false;
  }

  /* ---------- controls ---------- */

  function syncControls() {
    const found = selected();
    const node = found ? found.node : null;
    const undoButton = root.querySelector("[data-drawing-undo]");
    const redoButton = root.querySelector("[data-drawing-redo]");
    if (undoButton) undoButton.disabled = !editable || !history.canUndo;
    if (redoButton) redoButton.disabled = !editable || !history.canRedo;
    root.querySelectorAll("[data-style]").forEach((input) => {
      const name = input.dataset.style;
      if (name === "fill") input.value = (node && node.fill) || "#e0a327";
      if (name === "stroke") input.value = (node && node.stroke) || "#17150f";
      if (name === "strokeWidth") input.value = node?.strokeWidth ?? 4;
      if (name === "opacity") input.value = node ? Math.round(node.opacity * 100) : 100;
      if (name === "no-fill") input.checked = !(node && node.fill);
      if (name === "no-stroke") input.checked = !(node && node.stroke);
      input.disabled = !editable || !node || node.kind === "group";
    });
    root.querySelectorAll("[data-style-value]").forEach((output) => {
      const name = output.dataset.styleValue;
      if (name === "strokeWidth") output.textContent = node?.strokeWidth ?? 4;
      if (name === "opacity") output.textContent = `${node ? Math.round(node.opacity * 100) : 100}%`;
    });
    root.querySelectorAll("[data-palette]").forEach((chip) => {
      chip.disabled = !editable || !node || node.kind === "group";
    });
    const fillSwatch = root.querySelector("[data-testid='drawing-fill-swatch']");
    if (fillSwatch) fillSwatch.style.setProperty("--swatch", (node && node.fill) || "transparent");
    const strokeSwatch = root.querySelector("[data-testid='drawing-stroke-swatch']");
    if (strokeSwatch) strokeSwatch.style.setProperty("--swatch", (node && node.stroke) || "transparent");
    root.querySelectorAll("[data-drawing-duplicate],[data-drawing-delete],[data-drawing-order],[data-drawing-mode],[data-drawing-ungroup],[data-node-name]").forEach((control) => {
      control.disabled = !editable || !node;
    });
    const groupButton = root.querySelector("[data-drawing-group]");
    if (groupButton) groupButton.disabled = !editable || selection.length < 2;
    const ungroupButton = root.querySelector("[data-drawing-ungroup]");
    if (ungroupButton) ungroupButton.disabled = !editable || !node || node.kind !== "group";
    const parentInput = root.querySelector("[data-node-parent]");
    if (parentInput) {
      const options = [new Option("Scena", "")];
      walk(scene.nodes, candidate => {
        if (candidate.kind === "group" && node && candidate.id !== node.id && !(ancestorsOf(candidate.id) || []).includes(node.id)) options.push(new Option(candidate.name, candidate.id));
      });
      parentInput.replaceChildren(...options);
      parentInput.value = found?.parent?.id || "";
      parentInput.disabled = !editable || !node || selection.length !== 1;
    }
    const nameInput = root.querySelector("[data-node-name]");
    if (nameInput && document.activeElement !== nameInput) nameInput.value = node?.name || "";
    const issues = visibilityIssues(scene, selectedId), descriptions = {"no-selection":"Nessuna selezione", hidden:"Oggetto nascosto", "hidden-parent":"Nascosto dal genitore", "zero-opacity":"Opacità zero", "empty-group":"Gruppo vuoto · conservato", "no-paint":"Riempimento e contorno disattivati"};
    root.querySelector("[data-drawing-diagnostics]").textContent = issues.map(issue => descriptions[issue]).join(" · ") || "Visibilità attiva";
    root.querySelectorAll("[data-drawing-action]").forEach(control => { control.disabled = !canExecute(control.dataset.drawingAction); });
    root.querySelectorAll("[data-drawing-mode]").forEach(button => {
      const active = tool === "select" && mode === button.dataset.drawingMode;
      button.classList.toggle("btn-selected", active);
      button.setAttribute("aria-pressed", String(active));
    });
    const selectButton = root.querySelector("[data-tool='select']");
    selectButton.classList.toggle("btn-selected", tool === "select" && mode === "select");
    selectButton.setAttribute("aria-pressed", String(tool === "select" && mode === "select"));
    root.querySelector("[data-drawing-mode-label]").textContent = tool === "select" ? {select:"Seleziona", vertex:"Modifica forma", transform:"Trasforma"}[mode] : PRESET_LABELS[creationPreset] || SHAPE_NAMES[tool] || (tool === "curve" ? "Curva" : "Taglia");
    root.querySelector("[data-ellipse-parameters]").hidden = selection.length !== 1 || node?.kind !== "ellipse";
    root.querySelectorAll("[data-ellipse-parameter]").forEach(input => {
      input.disabled = !canExecute("ellipse-parameter");
      input.closest("label").hidden = input.dataset.ellipseParameter === "ry" && node?.constraint?.kind === "circle";
      if (node?.kind === "ellipse" && document.activeElement !== input) input.value = round(node[input.dataset.ellipseParameter]);
    });
    const radiusLabel = node?.constraint?.kind === "circle" ? "Raggio" : "Raggio orizzontale";
    root.querySelector("[data-ellipse-radius-label]").textContent = radiusLabel;
    root.querySelector("[data-ellipse-parameter='rx']").setAttribute("aria-label", radiusLabel);
    root.querySelector("[data-regular-options]").hidden = tool !== "regular";
    root.querySelectorAll("[data-drawing-preset]").forEach(button => { button.disabled = !canExecute(`preset-${button.dataset.drawingPreset}`); });
    const constraint = root.querySelector("[data-drawing-constraint]");
    constraint.hidden = !node || node.kind === "group";
    constraint.textContent = node?.constraint ? `Geometria vincolata · ${PRESET_LABELS[node.constraint.kind] || "Cerchio"}` : "Geometria libera";
    root.querySelector("[data-drawing-unlock]").hidden = !node?.constraint;
    const hint = root.querySelector("[data-testid='drawing-inspector-hint']");
    if (hint) hint.hidden = Boolean(node);
  }

  function wire() {
    const grid = root.querySelector("[data-drawing-grid]");
    grid.addEventListener("click", () => {
      const on = grid.getAttribute("aria-pressed") !== "true";
      grid.setAttribute("aria-pressed", String(on));
      grid.dataset.off = on ? "" : "true";
      svg.querySelector(".drawing-editor__grid").style.display = on ? "" : "none";
    });
    for (const kind of ["grid", "shapes"]) {
      const button = root.querySelector(`[data-snap-${kind}]`);
      button.addEventListener("click", () => {
        const on = button.getAttribute("aria-pressed") !== "true";
        if (kind === "grid") snapGrid = on;
        else snapShapes = on;
        button.setAttribute("aria-pressed", String(on));
        button.classList.toggle("btn-selected", on);
      });
    }
    const titleInput = root.querySelector("[data-drawing-title]");
    if (titleInput) titleInput.addEventListener("input", () => { title = titleInput.value.trim(); refresh(); });
    root.querySelector("[data-drawing-save-copy]").addEventListener("click", () => save(true));
    root.querySelector("[data-drawing-reload]").addEventListener("click", () => { allowLeave = true; window.location.assign(window.location.href); });
    root.querySelectorAll("[data-tool]").forEach((button) => {
      const id = button.dataset.tool === "select" ? "select" : `tool-${button.dataset.tool}`;
      button.dataset.drawingAction = id;
      button.addEventListener("click", () => execute(id));
    });
    root.querySelectorAll("[data-drawing-preset]").forEach(button => {
      button.dataset.drawingAction = `preset-${button.dataset.drawingPreset}`;
      button.addEventListener("click", () => execute(button.dataset.drawingAction));
    });
    root.querySelectorAll("[data-ellipse-parameter]").forEach(input => {
      input.addEventListener("change", () => execute("ellipse-parameter", {field:input.dataset.ellipseParameter, value:input.valueAsNumber}));
    });
    root.querySelector("[data-regular-sides]").addEventListener("change", event => {
      const value = Number(event.target.value);
      if (Number.isInteger(value) && value >= 3 && value <= 32) regularSides = value;
      else { event.target.value = regularSides; announce("Scegli da 3 a 32 lati."); }
    });
    root.querySelectorAll("[data-drawing-command]").forEach(button => {
      button.dataset.drawingAction = button.dataset.drawingCommand;
      button.addEventListener("click", () => {
        contextMenu.hidePopover();
        execute(button.dataset.drawingCommand);
        svg.focus({preventScroll:true});
      });
    });
    const contextTrigger = root.querySelector("[data-drawing-context]");
    contextTrigger.addEventListener("click", () => { contextPosition = null; contextOpener = contextTrigger; });
    contextMenu.addEventListener("toggle", positionContext);
    contextMenu.addEventListener("keydown", event => {
      if (event.key !== "Escape") return;
      event.preventDefault(); event.stopPropagation();
      contextMenu.hidePopover();
      (contextOpener?.isConnected ? contextOpener : svg).focus({preventScroll:true});
    });
    window.addEventListener("resize", positionContext);
    window.addEventListener("scroll", positionContext, true);
    root.addEventListener("contextmenu", event => {
      if (!editable || root.dataset.copying || event.shiftKey || event.target.closest("input, textarea, select, [contenteditable]") || !event.target.closest("[data-drawing-artboard], [data-testid='drawing-layers']")) return;
      event.preventDefault();
      if (drag || cut) return;
      const row = event.target.closest("[data-node-id]");
      const id = row?.dataset.nodeId || (svg.contains(event.target) ? nodeAt(scene, scenePoint(event))?.id : null);
      if (id && !selection.includes(id) && !selectedAncestorOf(id)) select(id);
      openContext([event.clientX, event.clientY]);
    });
    const bindings = {
      "[data-drawing-undo]": "undo", "[data-drawing-redo]": "redo", "[data-testid='drawing-save']": "save",
      "[data-drawing-duplicate]": "duplicate", "[data-drawing-delete]": "delete", "[data-drawing-group]": "group",
      "[data-drawing-ungroup]": "ungroup", "[data-drawing-mode='vertex']": "edit", "[data-drawing-mode='transform']": "transform",
      "[data-drawing-order='1']": "forward", "[data-drawing-order='-1']": "backward", "[data-drawing-order='front']": "front", "[data-drawing-order='back']": "back", "[data-drawing-unlock]": "unlock",
    };
    for (const [selector, id] of Object.entries(bindings)) {
      root.querySelectorAll(selector).forEach(button => {
        button.dataset.drawingAction = id;
        button.addEventListener("click", () => execute(id));
      });
    }
    const parentInput = root.querySelector("[data-node-parent]");
    parentInput.addEventListener("change", () => {
      const result = reparentNode(scene, selectedId, parentInput.value || null);
      if (result) commit(result.scene);
      else { announce("Il genitore non è valido: controlla la gerarchia e la profondità."); syncControls(); }
    });
    const nameInput = root.querySelector("[data-node-name]");
    if (nameInput) {
      nameInput.addEventListener("change", () => renameSelected(nameInput.value));
    }

    root.querySelectorAll("[data-palette]").forEach((chip) => {
      chip.addEventListener("click", () => applyStyle(selected().node.kind === "path" ? { stroke: chip.dataset.palette } : { fill: chip.dataset.palette }));
    });
    const fillInput = root.querySelector("[data-style='fill']");
    if (fillInput) fillInput.addEventListener("change", () => applyStyle({ fill: fillInput.value }));
    const strokeInput = root.querySelector("[data-style='stroke']");
    if (strokeInput) strokeInput.addEventListener("change", () => applyStyle({ stroke: strokeInput.value }));
    const widthInput = root.querySelector("[data-style='strokeWidth']");
    if (widthInput) widthInput.addEventListener("change", () => applyStyle({ strokeWidth: Number(widthInput.value) }));
    const opacityInput = root.querySelector("[data-style='opacity']");
    if (opacityInput) opacityInput.addEventListener("change", () => applyStyle({ opacity: Number(opacityInput.value) / 100 }));
    const noFill = root.querySelector("[data-style='no-fill']");
    if (noFill) noFill.addEventListener("change", () => applyStyle({ fill: noFill.checked ? null : "#e0a327" }));
    const noStroke = root.querySelector("[data-style='no-stroke']");
    if (noStroke) noStroke.addEventListener("change", () => applyStyle({ stroke: noStroke.checked ? null : "#17150f" }));

    root.querySelectorAll("[data-select-node]").forEach((button) => {
      button.addEventListener("click", () => select(button.dataset.selectNode));
    });
    // The layer rows are rebuilt on every change, so their events are delegated.
    const layers = root.querySelector("[data-testid='drawing-layers']");
    if (layers) {
      layers.addEventListener("click", (event) => {
        const button = event.target.closest("[data-select-node]");
        if (button) select(button.dataset.selectNode, event.shiftKey);
        const eye = event.target.closest("[data-node-visible]");
        if (eye) {
          const node = findNode(scene, eye.dataset.nodeVisible).node;
          commit(patchNode(scene, node.id, {visible: !node.visible}));
        }
        const branch = event.target.closest("[data-node-collapse]");
        if (branch) {
          const id = branch.dataset.nodeCollapse;
          if (collapsed.has(id)) collapsed.delete(id);
          else collapsed.add(id);
          renderLayers();
        }
      });
      layers.addEventListener("keydown", event => {
        if (!event.target.matches("[data-select-node]")) return;
        const buttons = [...layers.querySelectorAll("[data-select-node]")].filter(button => button.getClientRects().length);
        const index = buttons.indexOf(event.target);
        if (["ArrowDown", "ArrowUp", "ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
          event.stopPropagation(); event.preventDefault();
          const id = event.target.dataset.selectNode;
          const found = findNode(scene, id);
          if (event.key === "ArrowLeft") {
            if (found.node.kind === "group" && !collapsed.has(id)) { collapsed.add(id); renderLayers(); }
            else if (found.parent) [...buttons].find(button => button.dataset.selectNode === found.parent.id)?.focus();
          } else if (event.key === "ArrowRight") {
            if (found.node.kind === "group" && collapsed.has(id)) { collapsed.delete(id); renderLayers(); }
            else buttons[Math.min(buttons.length - 1, index + 1)].focus();
          } else {
            const next = event.key === "Home" ? 0 : event.key === "End" ? buttons.length - 1 : index + (event.key === "ArrowDown" ? 1 : -1);
            buttons[Math.max(0, Math.min(buttons.length - 1, next))].focus();
          }
        }
      });
    }

    svg.addEventListener("pointerdown", onPointerDown);
    svg.addEventListener("pointermove", onPointerMove);
    svg.addEventListener("pointerup", onPointerUp);
    svg.addEventListener("pointercancel", () => {
      if (gestureBefore) scene = gestureBefore;
      drag = null;
      snapPoint = null;
      snapGuides = [];
      draw();
    });
    svg.addEventListener("click", event => {
      if (tool === "polygon" && event.detail === 1 && event.button === 0 && !spaceDown) addPolygonPoint(event);
    });
    svg.addEventListener("dblclick", (event) => {
      if (!editable || spaceDown) return;
      if (tool === "polygon" && pendingPolygon) {
        event.preventDefault();
        finishPolygon();
        return;
      }
      if (tool !== "select" || mode !== "vertex" || selection.length !== 1 || event.target.closest("[data-edge], [data-vertex], [data-path-command], [data-ellipse-axis]")) return;
      const node = selected().node, local = apply(invert(nodeFrame(scene, selectedId).world), scenePoint(event));
      if (node.kind === "polygon") {
        const hit = closestEdge(node, local, SNAP_TOLERANCE_PX / viewport[0]);
        if (hit) { event.preventDefault(); insertVertex(hit.edge, hit.point); }
      } else if (node.kind === "path") {
        const commands = pathCommands(node.d);
        let previous = commands[0].numbers.slice(0, 2);
        for (let index = 1; index < commands.length; index += 1) {
          const command = commands[index], end = command.numbers.slice(-2);
          if (command.name === "L" && distanceToSegment(local, previous, end) < SNAP_TOLERANCE_PX / viewport[0]) {
            event.preventDefault();
            const dx = end[0] - previous[0], dy = end[1] - previous[1];
            const t = clamp(((local[0] - previous[0]) * dx + (local[1] - previous[1]) * dy) / (dx * dx + dy * dy || 1), 0, 1);
            const pointIds = [...node.pointIds], position = commands.slice(0, index).reduce((count, entry) => count + entry.numbers.length / 2, 0);
            pointIds.splice(position, 0, newId("h"));
            commands.splice(index, 0, {name:"L", numbers:[previous[0] + t * dx, previous[1] + t * dy].map(round)});
            commit(patchNode(scene, selectedId, {d:commands.map(c => c.name + c.numbers.join(" ")).join(" "), pointIds}));
            return;
          }
          previous = end;
        }
      }
    });
    svg.addEventListener("wheel", onWheel, { passive: false });
    // On the document: only the focused workspace owns editor shortcuts;
    // clicking a shape focuses the artboard without scrolling the page.
    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("keydown", (event) => {
      if (editable && !document.querySelector("dialog[open]") && event.code === "Space" && (event.target === root || event.target === svg)) { spaceDown = true; event.preventDefault(); }
    });
    document.addEventListener("keyup", (event) => {
      if (event.code === "Space") spaceDown = false;
    });
    window.addEventListener("blur", () => { spaceDown = false; });
    window.addEventListener("beforeunload", (event) => {
      if (allowLeave || !isDirty()) return;
      event.preventDefault();
      event.returnValue = "";
    });
  }

  return {
    mount() {
      // A read-only specimen keeps the server-rendered markup untouched.
      if (!editable) {
        if (root.dataset.readonly !== "true") {
          draw();
          root.querySelectorAll("button, input").forEach(control => { control.disabled = true; });
        }
        return;
      }
      wire();
      draw();
      refresh();
    },
    save,
    undo,
    redo,
    isDirty,
    get scene() {
      return scene;
    },
    get selectedId() {
      return selectedId;
    },
    get selection() {
      return [...selection];
    },
    get tool() {
      return tool;
    },
    get cut() {
      return cut;
    },
    setTool,
    select,
    execute,
    canExecute,
    get actions() { return Object.entries(actions).map(([id, action]) => ({ id, label: action.label, enabled: canExecute(id) })); },
    get mode() { return mode; },
    palette: PALETTE,
  };
}
