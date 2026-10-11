/* The drawing editor controller: tools, selection, transforms, styles, history
   and the explicit save.

   One controller owns one workspace. Interaction writes the in-memory document
   and re-renders; nothing is sent to the server until an explicit save, and a
   completed gesture is the unit of undo, never a pointer move. */

import {
  apply,
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
  duplicateNode,
  findNode,
  nodeAt,
  nodeBounds,
  patchNode,
  removeNode,
  reorderNode,
  setTransform,
  validPolygon,
} from "./scene.js";
import { render } from "./render.js";

const PALETTE = [
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
  const editable = root.dataset.readonly !== "true";

  let scene = sceneScript ? JSON.parse(sceneScript.textContent) : { schemaVersion: 1, artboard: { width: 640, height: 480, background: "#fffdf6" }, nodes: [] };
  const history = new History(scene);
  let selectedId = null;
  let tool = "select";
  let mode = "transform";
  let viewport = [1, 0, 0, 1, 0, 0];
  let drag = null;
  let pendingPolygon = null;

  let savedScene = canonical(scene);
  let savedVersion = Number(root.dataset.version || 0) || null;
  let inFlight = false;

  /* ---------- rendering ---------- */

  function view() {
    return { selectedId, viewport, mode, tool };
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
        row.className = "drawing-editor__layer" + (node.id === selectedId ? " is-selected" : "");
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
        button.setAttribute("aria-pressed", String(node.id === selectedId));
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

  /* ---------- history ---------- */

  function commit(next) {
    history.commit(next);
    scene = history.present;
    if (selectedId && !findNode(scene, selectedId)) selectedId = null;
    draw();
  }

  function undo() {
    if (!history.canUndo) return;
    scene = history.undo();
    if (selectedId && !findNode(scene, selectedId)) selectedId = null;
    draw();
  }

  function redo() {
    if (!history.canRedo) return;
    scene = history.redo();
    if (selectedId && !findNode(scene, selectedId)) selectedId = null;
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
    return canonical(scene) !== savedScene;
  }

  function refresh() {
    root.dataset.dirty = isDirty() ? "true" : "false";
    if (root.dataset.saving === "true") return;
    status(isDirty() ? "Modifiche non salvate" : "Salvato", isDirty() ? "dirty" : "saved");
  }

  async function save() {
    if (!saveUrl || inFlight) return;
    inFlight = true;
    root.dataset.saving = "true";
    status("Salvataggio…", "saving");
    announce("");
    let saved = false;
    try {
      const response = await fetch(saveUrl, {
        method: "PATCH",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ expectedVersion: savedVersion, scene }),
      });
      if (!response.ok) {
        announce(errorMessage(response.status));
        return;
      }
      const updated = await response.json();
      savedScene = canonical(updated.scene);
      savedVersion = updated.version;
      saved = true;
    } catch (error) {
      announce("Rete non raggiungibile. Il disegno non è stato salvato.");
    } finally {
      inFlight = false;
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
    ].map((point) => apply(node.transform, point));
  }

  /* ---------- tools ---------- */

  function setTool(next) {
    tool = next;
    pendingPolygon = null;
    if (next === "select") mode = "transform";
    root.querySelectorAll("[data-tool]").forEach((button) => {
      button.classList.toggle("is-selected", button.dataset.tool === next);
      button.setAttribute("aria-pressed", String(button.dataset.tool === next));
    });
    draw();
  }

  function setMode(next) {
    mode = next;
    if (next === "vertex" && tool !== "select") setTool("select");
    draw();
  }

  function select(id) {
    selectedId = id;
    if (!id) mode = "transform";
    draw();
  }

  function beginShape(event) {
    drag = { kind: "create", tool, from: scenePoint(event), to: scenePoint(event) };
  }

  function finishShape() {
    if (!drag) return;
    const { from, to, tool: shape } = drag;
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
    selectedId = node.id;
    setTool("select");
  }

  function beginLine(event) {
    drag = { kind: "line", from: scenePoint(event), to: scenePoint(event) };
  }

  function finishLine() {
    if (!drag) return;
    const { from, to } = drag;
    drag = null;
    if (Math.hypot(to[0] - from[0], to[1] - from[1]) < 4) return;
    const node = createPath("Linea", `M${round(from[0])} ${round(from[1])} L${round(to[0])} ${round(to[1])}`);
    commit(addNode(scene, node));
    selectedId = node.id;
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
      announce("Il poligono non ha area: aggiungi altri punti.");
      return;
    }
    const node = createPolygon("Poligono", pendingPolygon);
    pendingPolygon = null;
    announce("");
    commit(addNode(scene, node));
    selectedId = node.id;
    setTool("select");
  }

  function cancelPolygon() {
    pendingPolygon = null;
    announce("");
    draw();
  }

  /* ---------- pointer ---------- */

  function onPointerDown(event) {
    if (!editable) return;
    svg.setPointerCapture(event.pointerId);
    const target = event.target;

    if (event.button === 1 || (event.button === 0 && event.shiftKey && tool === "select" && !target.dataset.vertex)) {
      drag = { kind: "pan", from: artboardPoint(event), pan: [viewport[4], viewport[5]] };
      return;
    }
    if (event.button !== 0) return;

    if (target.dataset.vertex !== undefined && mode === "vertex" && selectedId) {
      const node = selected().node;
      drag = { kind: "vertex", id: selectedId, index: Number(target.dataset.vertex), transform: node.transform, points: node.points.map((point) => [...point]) };
      return;
    }
    if (target.dataset.corner !== undefined && selectedId) {
      const node = selected().node;
      drag = { kind: "scale", id: selectedId, corner: Number(target.dataset.corner), transform: node.transform, corners: worldCorners(node), from: scenePoint(event) };
      return;
    }
    if (target.classList.contains("drawing-editor__rotate-handle") && selectedId) {
      const node = selected().node;
      const corners = worldCorners(node);
      const center = [(corners[0][0] + corners[2][0]) / 2, (corners[0][1] + corners[2][1]) / 2];
      drag = { kind: "rotate", id: selectedId, transform: node.transform, center, start: Math.atan2(scenePoint(event)[1] - center[1], scenePoint(event)[0] - center[0]) };
      return;
    }

    if (tool === "polygon") {
      addPolygonPoint(event);
      return;
    }
    if (tool === "line") {
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
    if (hit.id !== selectedId) select(hit.id);
    drag = { kind: "move", id: hit.id, from: scenePoint(event), transform: hit.transform };
  }

  function onPointerMove(event) {
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
      const next = setTransform(scene, drag.id, multiply(translation(point[0] - drag.from[0], point[1] - drag.from[1]), drag.transform));
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
      scene = setTransform(scene, drag.id, multiply(scaleAbout(fixed, clampFactor(sx), clampFactor(sy)), drag.transform));
      draw();
      return;
    }
    if (drag.kind === "rotate") {
      const point = scenePoint(event);
      const angle = Math.atan2(point[1] - drag.center[1], point[0] - drag.center[0]) - drag.start;
      scene = setTransform(scene, drag.id, multiply(rotateAbout(drag.center, angle), drag.transform));
      draw();
      return;
    }
    if (drag.kind === "vertex") {
      const inverse = invert(drag.transform);
      if (!inverse) return;
      const local = apply(inverse, scenePoint(event));
      const points = drag.points.map((point, index) => (index === drag.index ? [round(local[0]), round(local[1])] : point));
      if (!validPolygon(points)) return;
      scene = patchNode(scene, drag.id, { points });
      draw();
    }
  }

  function onPointerUp() {
    if (!drag) return;
    const finished = drag;
    if (finished.kind === "create") finishShape();
    else if (finished.kind === "line") finishLine();
    else if (finished.kind === "move" || finished.kind === "scale" || finished.kind === "rotate" || finished.kind === "vertex") {
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
    if (!editable) return;
    if (event.target instanceof HTMLInputElement) return;
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
      const node = selected().node;
      commit(setTransform(scene, selectedId, multiply(translation(dx, dy), node.transform)));
    }
  }

  /* ---------- actions ---------- */

  function deleteSelected() {
    if (!selectedId) return;
    commit(removeNode(scene, selectedId));
    selectedId = null;
    draw();
  }

  function duplicateSelected() {
    if (!selectedId) return;
    const result = duplicateNode(scene, selectedId);
    commit(result.scene);
    selectedId = result.id;
    draw();
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
      if (name === "strokeWidth") input.value = node ? node.strokeWidth : 4;
      if (name === "opacity") input.value = node ? Math.round(node.opacity * 100) : 100;
      if (name === "no-fill") input.checked = !(node && node.fill);
      if (name === "no-stroke") input.checked = !(node && node.stroke);
      input.disabled = !editable || !node;
    });
    root.querySelectorAll("[data-style-value]").forEach((output) => {
      const name = output.dataset.styleValue;
      if (name === "strokeWidth") output.textContent = node ? node.strokeWidth : 4;
      if (name === "opacity") output.textContent = `${node ? Math.round(node.opacity * 100) : 100}%`;
    });
    root.querySelectorAll("[data-palette]").forEach((chip) => {
      chip.disabled = !editable || !node;
    });
    const fillSwatch = root.querySelector("[data-testid='drawing-fill-swatch']");
    if (fillSwatch) fillSwatch.style.setProperty("--swatch", (node && node.fill) || "transparent");
    const strokeSwatch = root.querySelector("[data-testid='drawing-stroke-swatch']");
    if (strokeSwatch) strokeSwatch.style.setProperty("--swatch", (node && node.stroke) || "transparent");
    root.querySelectorAll("[data-drawing-duplicate],[data-drawing-delete],[data-drawing-order],[data-drawing-mode]").forEach((button) => {
      button.disabled = !editable || !node;
    });
    const modeButton = root.querySelector("[data-drawing-mode]");
    if (modeButton) {
      modeButton.classList.toggle("btn-selected", mode === "vertex");
      modeButton.setAttribute("aria-pressed", String(mode === "vertex"));
    }
    const hint = root.querySelector("[data-testid='drawing-inspector-hint']");
    if (hint) hint.hidden = Boolean(node);
  }

  function wire() {
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
    root.querySelectorAll("[data-drawing-order]").forEach((button) => {
      button.addEventListener("click", () => {
        if (!selectedId) return;
        commit(reorderNode(scene, selectedId, Number(button.dataset.drawingOrder)));
      });
    });
    const modeButton = root.querySelector("[data-drawing-mode]");
    if (modeButton) modeButton.addEventListener("click", () => setMode(mode === "vertex" ? "transform" : "vertex"));

    root.querySelectorAll("[data-palette]").forEach((chip) => {
      chip.addEventListener("click", () => applyStyle({ fill: chip.dataset.palette }));
    });
    const fillInput = root.querySelector("[data-style='fill']");
    if (fillInput) fillInput.addEventListener("input", () => applyStyle({ fill: fillInput.value }));
    const strokeInput = root.querySelector("[data-style='stroke']");
    if (strokeInput) strokeInput.addEventListener("input", () => applyStyle({ stroke: strokeInput.value }));
    const widthInput = root.querySelector("[data-style='strokeWidth']");
    if (widthInput) widthInput.addEventListener("input", () => applyStyle({ strokeWidth: Number(widthInput.value) }));
    const opacityInput = root.querySelector("[data-style='opacity']");
    if (opacityInput) opacityInput.addEventListener("input", () => applyStyle({ opacity: Number(opacityInput.value) / 100 }));
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
        if (button) select(button.dataset.selectNode);
      });
      layers.addEventListener("change", (event) => {
        const check = event.target.closest("[data-node-visible]");
        if (check) commit(patchNode(scene, check.dataset.nodeVisible, { visible: check.checked }));
      });
    }

    svg.addEventListener("pointerdown", onPointerDown);
    svg.addEventListener("pointermove", onPointerMove);
    svg.addEventListener("pointerup", onPointerUp);
    svg.addEventListener("pointercancel", onPointerUp);
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
    window.addEventListener("beforeunload", (event) => {
      if (!isDirty()) return;
      event.preventDefault();
      event.returnValue = "";
    });
  }

  return {
    mount() {
      // A read-only specimen keeps the server-rendered markup untouched.
      if (!editable) return;
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
    setTool,
    select,
    palette: PALETTE,
  };
}
