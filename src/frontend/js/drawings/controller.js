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
  translation,
} from "./geometry.js";
import {
  History,
  addNode,
  createEllipse,
  createPath,
  createPolygon,
  createRect,
  cutNode,
  duplicateNode,
  findNode,
  groupNodes,
  nodeAt,
  nodeBounds,
  nodeFrame,
  movePathPoint,
  pathCommands,
  patchNode,
  removeNode,
  reorderNode,
  setTransform,
  transformInWorld,
  ungroupNode,
  validPolygon,
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
  line: "Linea",
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
  const editable = root.dataset.readonly !== "true" && !window.matchMedia("(max-width: 900px)").matches;

  let scene = sceneScript ? JSON.parse(sceneScript.textContent) : { schemaVersion: 1, artboard: { width: 640, height: 480, background: "#fffdf6" }, nodes: [] };
  const history = new History(scene);
  let selection = [];
  let selectedId = null;
  let tool = "select";
  let mode = "transform";
  let viewport = [1, 0, 0, 1, 0, 0];
  let drag = null;
  let pendingPolygon = null;
  let snapPoint = null;
  let cut = null;
  let cutCursor = null;
  let spaceDown = false;
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
      tool,
      snap: snapPoint,
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
    const rows = [];
    const flatten = (nodes, depth) => {
      for (const node of nodes) {
        const row = document.createElement("li");
        row.className = "drawing-editor__layer" + (selection.includes(node.id) ? " is-selected" : "");
        row.dataset.nodeId = node.id;
        if (depth) row.style.setProperty("--drawing-depth", String(depth));

        const check = document.createElement("input");
        check.type = "checkbox";
        check.className = "drawing-editor__layer-check";
        check.checked = node.visible !== false;
        check.disabled = !editable;
        check.setAttribute("aria-label", `Mostra ${node.name}`);
        check.dataset.nodeVisible = node.id;
        row.appendChild(check);

        const button = document.createElement("button");
        button.type = "button";
        button.className = "drawing-editor__layer-name";
        button.textContent = node.name;
        button.dataset.selectNode = node.id;
        button.dataset.testid = "drawing-layer";
        button.setAttribute("aria-pressed", String(selection.includes(node.id)));
        row.appendChild(button);
        rows.push(row);
        if (node.kind === "group") flatten(node.nodes, depth + 1);
      }
    };
    flatten(scene.nodes, 0);
    if (!rows.length) {
      const empty = document.createElement("li");
      empty.className = "drawing-editor__empty hint";
      empty.textContent = "Nessun oggetto";
      rows.push(empty);
    }
    list.replaceChildren(...rows);
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
    const box = nodeBounds(node);
    return [
      [box.minX, box.minY],
      [box.maxX, box.minY],
      [box.maxX, box.maxY],
      [box.minX, box.maxY],
    ].map((point) => apply(nodeFrame(scene, node.id).world, point));
  }

  /* ---------- snapping ---------- */

  const SNAP_TOLERANCE_PX = 8;
  const SNAP_GRID = 10;

  /** Snap a world point to the grid or a sibling vertex; Alt bypasses it. */
  function snapWorld(point, node, excludeIndex, bypass) {
    if (bypass) return { point, snapped: false };
    const tolerance = SNAP_TOLERANCE_PX / (viewport[0] * Math.abs(svg.getScreenCTM().a));
    let best = null;
    let bestDistance = tolerance;
    walk(scene.nodes, candidate => {
      if (candidate.visible === false || (ancestorsOf(candidate.id) || []).some(id => !findNode(scene, id).node.visible)) return;
      const points = candidate.kind === "polygon" ? candidate.points : candidate.kind === "path" ? pathHandles(candidate.d).filter(h => !h.control).map(h => h.point) : [];
      const world = nodeFrame(scene, candidate.id).world;
      const targets = points.filter((p, i) => candidate.id !== node?.id || i !== excludeIndex);
      if (candidate.kind === "polygon") targets.push(...points.map((p, i) => [(p[0] + points[(i + 1) % points.length][0]) / 2, (p[1] + points[(i + 1) % points.length][1]) / 2]));
      targets.forEach(local => {
        const vertex = apply(world, local);
        const distance = Math.hypot(vertex[0] - point[0], vertex[1] - point[1]);
        if (distance < bestDistance) { bestDistance = distance; best = vertex; }
      });
    });
    const gridX = Math.round(point[0] / SNAP_GRID) * SNAP_GRID;
    const gridY = Math.round(point[1] / SNAP_GRID) * SNAP_GRID;
    if (!root.querySelector("[data-drawing-grid]")?.dataset.off && Math.hypot(gridX - point[0], gridY - point[1]) < bestDistance) {
      best = [gridX, gridY];
    }
    return best ? { point: best, snapped: true } : { point, snapped: false };
  }

  /* ---------- vertex editing ---------- */

  function edgeVisibility(node) {
    return node.edgeVisible ? [...node.edgeVisible] : node.points.map(() => true);
  }

  function insertVertex(edgeIndex, localPoint) {
    const node = selected().node;
    const points = node.points.map((point) => [...point]);
    points.splice(edgeIndex + 1, 0, [round(localPoint[0]), round(localPoint[1])]);
    if (!validPolygon(points)) return;
    const patch = { points };
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
    if (node.points.length <= 3) {
      announce("Un poligono ha almeno tre vertici.");
      return;
    }
    const points = node.points.filter((_, position) => position !== index);
    if (!validPolygon(points)) {
      announce("Il poligono perderebbe la sua area.");
      return;
    }
    const patch = { points };
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
    const patch = { points };
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
    // Vertex handles belong to the select tool; a tool switch leaves that mode.
    mode = "transform";
    root.querySelectorAll("[data-tool]").forEach((button) => {
      button.classList.toggle("is-selected", button.dataset.tool === next);
      button.setAttribute("aria-pressed", String(button.dataset.tool === next));
    });
    draw();
  }

  function setMode(next) {
    if (next === "vertex" && tool !== "select") setTool("select");
    mode = next;
    draw();
  }

  function select(id, additive = false) {
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
    if (selection.length !== 1) mode = "transform";
    draw();
  }

  /** Select exactly these ids; used by the actions that produce new shapes. */
  function setSelection(ids) {
    selection = ids.filter((id) => Boolean(findNode(scene, id)));
    selectedId = selection.length ? selection[0] : null;
  }

  function beginShape(event) {
    drag = { kind: "create", tool, from: scenePoint(event), to: scenePoint(event) };
  }

  function finishShape() {
    if (!drag) return;
    const { tool: shape } = drag;
    const from = snapWorld(drag.from, null, -1, false).point;
    const to = snapWorld(drag.to, null, -1, false).point;
    drag = null;
    const minX = Math.min(from[0], to[0]);
    const maxX = Math.max(from[0], to[0]);
    const minY = Math.min(from[1], to[1]);
    const maxY = Math.max(from[1], to[1]);
    if (maxX - minX < 4 || maxY - minY < 4) return;
    const name = SHAPE_NAMES[shape] || "Forma";
    let node = null;
    if (shape === "triangle") {
      node = createPolygon(name, [[minX, maxY], [maxX, maxY], [(minX + maxX) / 2, minY]]);
    } else if (shape === "square") {
      node = createRect(name, [minX, minY], [maxX, maxY]);
    } else if (shape === "circle") {
      node = createEllipse(name, [(minX + maxX) / 2, (minY + maxY) / 2], (maxX - minX) / 2, (maxY - minY) / 2);
    }
    if (!node) return;
    commit(addNode(scene, node));
    setSelection([node.id]);
    setTool("select");
  }

  function beginLine(event) {
    drag = { kind: "line", curve: tool === "curve", from: scenePoint(event), to: scenePoint(event) };
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
    const point = scenePoint(event);
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
    if (!editable || root.dataset.copying) return;
    svg.setPointerCapture(event.pointerId);
    gestureBefore = scene;
    const target = event.target;
    if (target.dataset.pathCommand !== undefined && mode === "vertex" && selectedId) {
      const node = selected().node;
      drag = { kind: "path", id: selectedId, command: Number(target.dataset.pathCommand), offset: Number(target.dataset.pathOffset), d: node.d, transform: nodeFrame(scene, selectedId).world };
      return;
    }

    // Pan with the middle button or with Space held: Shift belongs to
    // multi-selection, not to panning.
    if (event.button === 1 || (event.button === 0 && spaceDown)) {
      drag = { kind: "pan", from: artboardPoint(event), pan: [viewport[4], viewport[5]] };
      return;
    }
    if (event.button !== 0) return;

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
    if (mode === "vertex" && selectedId && tool === "select") {
      const node = selected().node;
      if (node.kind === "path") {
        const local = apply(invert(nodeFrame(scene, selectedId).world), scenePoint(event));
        const commands = pathCommands(node.d);
        let previous = commands[0].numbers.slice(0, 2);
        for (let index = 1; index < commands.length; index += 1) {
          const command = commands[index];
          const end = command.numbers.slice(-2);
          if (command.name === "L" && distanceToSegment(local, previous, end) < SNAP_TOLERANCE_PX / viewport[0]) {
            commands.splice(index, 0, { name: "L", numbers: local.map(round) });
            commit(patchNode(scene, selectedId, { d: commands.map(c => c.name + c.numbers.join(" ")).join(" ") }));
            return;
          }
          previous = end;
        }
      }
      if (node.kind === "polygon") {
        const inverse = invert(nodeFrame(scene, node.id).world);
        if (inverse) {
          const local = apply(inverse, scenePoint(event));
          const hit = closestEdge(node, local, SNAP_TOLERANCE_PX / viewport[0]);
          if (hit) {
            insertVertex(hit.edge, hit.point);
            return;
          }
        }
      }
    }
    // The transform handles belong to the select tool; another tool's clicks
    // must reach the canvas, not a handle sitting on the same corner.
    if (target.dataset.corner !== undefined && selectedId && tool === "select") {
      const node = selected().node;
      drag = { kind: "scale", id: selectedId, corner: Number(target.dataset.corner), transform: nodeFrame(scene, selectedId).world, corners: worldCorners(node), from: scenePoint(event) };
      return;
    }
    if (target.classList.contains("drawing-editor__rotate-handle") && selectedId && tool === "select") {
      const node = selected().node;
      const corners = worldCorners(node);
      const center = [(corners[0][0] + corners[2][0]) / 2, (corners[0][1] + corners[2][1]) / 2];
      drag = { kind: "rotate", id: selectedId, transform: nodeFrame(scene, selectedId).world, center, start: Math.atan2(scenePoint(event)[1] - center[1], scenePoint(event)[0] - center[0]) };
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
      drag.to = scenePoint(event);
      previewDrag();
      return;
    }
    if (drag.kind === "move") {
      const point = scenePoint(event);
      const delta = translation(point[0] - drag.from[0], point[1] - drag.from[1]);
      let next = scene;
      for (const entry of drag.transforms) {
        next = transformInWorld(next, entry.id, delta, entry.transform);
      }
      scene = next;
      draw();
      return;
    }
    if (drag.kind === "scale") {
      const point = scenePoint(event);
      const fixed = drag.corners[(drag.corner + 2) % 4];
      const start = drag.corners[drag.corner];
      let sx = (point[0] - fixed[0]) / (start[0] - fixed[0]);
      let sy = (point[1] - fixed[1]) / (start[1] - fixed[1]);
      if (!Number.isFinite(sx)) sx = 1;
      if (!Number.isFinite(sy)) sy = 1;
      scene = transformInWorld(scene, drag.id, scaleAbout(fixed, clampFactor(sx), clampFactor(sy)), drag.transform);
      draw();
      return;
    }
    if (drag.kind === "rotate") {
      const point = scenePoint(event);
      const angle = Math.atan2(point[1] - drag.center[1], point[0] - drag.center[0]) - drag.start;
      scene = transformInWorld(scene, drag.id, rotateAbout(drag.center, angle), drag.transform);
      draw();
      return;
    }
    if (drag.kind === "path") {
      const local = apply(invert(drag.transform), snapWorld(scenePoint(event), null, -1, event.altKey).point);
      scene = patchNode(scene, drag.id, { d: movePathPoint(drag.d, drag.command, drag.offset, local) });
      draw();
      return;
    }
    if (drag.kind === "vertex") {
      const inverse = invert(drag.transform);
      if (!inverse) return;
      const snapped = snapWorld(scenePoint(event), drag.node, drag.index, event.altKey);
      snapPoint = snapped.snapped ? snapped.point : null;
      const local = apply(inverse, snapped.point);
      const points = drag.points.map((point, index) => (index === drag.index ? [round(local[0]), round(local[1])] : point));
      if (!validPolygon(points)) return;
      scene = patchNode(scene, drag.id, { points });
      draw();
    }
  }

  function onPointerUp() {
    if (!drag) return;
    const finished = drag;
    snapPoint = null;
    if (finished.kind === "create") finishShape();
    else if (finished.kind === "line") finishLine();
    else if (finished.kind === "move" || finished.kind === "scale" || finished.kind === "rotate" || finished.kind === "vertex" || finished.kind === "path") {
      drag = null;
      commit(scene);
    } else {
      drag = null;
    }
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

  function onKeyDown(event) {
    if (!editable || root.dataset.copying || !root.isConnected || document.querySelector("dialog[open]")) return;
    if (event.target.closest("input, textarea, select, [contenteditable='true']")) return;
    const mod = event.ctrlKey || event.metaKey;
    if (mod && event.key.toLowerCase() === "s") {
      event.preventDefault();
      save();
      return;
    }
    if (mod && event.key.toLowerCase() === "z" && !event.shiftKey) {
      event.preventDefault();
      undo();
      return;
    }
    if (mod && (event.key.toLowerCase() === "y" || (event.key.toLowerCase() === "z" && event.shiftKey))) {
      event.preventDefault();
      redo();
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
      deleteSelected();
      return;
    }
    if (mod && event.key.toLowerCase() === "d") {
      event.preventDefault();
      duplicateSelected();
      return;
    }
    const nudge = event.shiftKey ? 10 : 1;
    const steps = { ArrowLeft: [-nudge, 0], ArrowRight: [nudge, 0], ArrowUp: [0, -nudge], ArrowDown: [0, nudge] };
    if (steps[event.key]) {
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
    const nameInput = root.querySelector("[data-node-name]");
    if (nameInput && node && document.activeElement !== nameInput) nameInput.value = node.name;
    const modeButton = root.querySelector("[data-drawing-mode]");
    if (modeButton) {
      modeButton.disabled = !editable || !node || node.kind === "group" || node.kind === "ellipse";
      modeButton.classList.toggle("btn-selected", mode === "vertex");
      modeButton.setAttribute("aria-pressed", String(mode === "vertex"));
    }
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
    const titleInput = root.querySelector("[data-drawing-title]");
    if (titleInput) titleInput.addEventListener("input", () => { title = titleInput.value.trim(); refresh(); });
    root.querySelector("[data-drawing-save-copy]").addEventListener("click", () => save(true));
    root.querySelector("[data-drawing-reload]").addEventListener("click", () => { allowLeave = true; window.location.assign(window.location.href); });
    root.querySelectorAll("[data-tool]").forEach((button) => {
      button.addEventListener("click", () => setTool(button.dataset.tool));
    });
    const undoButton = root.querySelector("[data-drawing-undo]");
    if (undoButton) undoButton.addEventListener("click", undo);
    const redoButton = root.querySelector("[data-drawing-redo]");
    if (redoButton) redoButton.addEventListener("click", redo);
    const saveButton = root.querySelector("[data-testid='drawing-save']");
    if (saveButton) saveButton.addEventListener("click", save);
    const duplicateButton = root.querySelector("[data-drawing-duplicate]");
    if (duplicateButton) duplicateButton.addEventListener("click", duplicateSelected);
    const deleteButton = root.querySelector("[data-drawing-delete]");
    if (deleteButton) deleteButton.addEventListener("click", deleteSelected);
    const groupButton = root.querySelector("[data-drawing-group]");
    if (groupButton) groupButton.addEventListener("click", groupSelected);
    const ungroupButton = root.querySelector("[data-drawing-ungroup]");
    if (ungroupButton) ungroupButton.addEventListener("click", ungroupSelected);
    const nameInput = root.querySelector("[data-node-name]");
    if (nameInput) {
      nameInput.addEventListener("change", () => renameSelected(nameInput.value));
    }
    root.querySelectorAll("[data-drawing-order]").forEach((button) => {
      button.addEventListener("click", () => {
        if (!selectedId) return;
        commit(reorderNode(scene, selectedId, Number(button.dataset.drawingOrder)));
      });
    });
    const modeButton = root.querySelector("[data-drawing-mode]");
    if (modeButton) modeButton.addEventListener("click", () => setMode(mode === "vertex" ? "transform" : "vertex"));

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
      });
      layers.addEventListener("change", (event) => {
        const check = event.target.closest("[data-node-visible]");
        if (check) commit(patchNode(scene, check.dataset.nodeVisible, { visible: check.checked }));
      });
    }

    svg.addEventListener("pointerdown", onPointerDown);
    svg.addEventListener("pointermove", onPointerMove);
    svg.addEventListener("pointerup", onPointerUp);
    svg.addEventListener("pointercancel", () => {
      if (gestureBefore) scene = gestureBefore;
      drag = null;
      snapPoint = null;
      draw();
    });
    svg.addEventListener("click", event => {
      if (tool === "polygon" && event.detail === 1 && event.button === 0 && !spaceDown) addPolygonPoint(event);
    });
    svg.addEventListener("dblclick", (event) => {
      if (tool === "polygon" && pendingPolygon) {
        event.preventDefault();
        finishPolygon();
      }
    });
    svg.addEventListener("wheel", onWheel, { passive: false });
    // On the document: the artboard is not focusable, so a keypress after
    // clicking a shape targets the body, not the workspace element.
    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("keydown", (event) => {
      if (event.code === "Space" && (event.target === document.body || event.target === root || event.target === svg)) { spaceDown = true; event.preventDefault(); }
    });
    document.addEventListener("keyup", (event) => {
      if (event.code === "Space") spaceDown = false;
    });
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
    palette: PALETTE,
  };
}
