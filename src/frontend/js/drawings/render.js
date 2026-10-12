/* The SVG renderer: the document as shapes plus the selection overlay.

   The renderer is a pure projection of the scene and the view — it holds no
   state. The scene layer carries the viewport transform so panning and zooming
   move the artwork; the overlay is drawn in artboard coordinates with the
   transform applied, so a handle stays the same size on screen. */

import { apply, multiply } from "./geometry.js";
import { nodeFrame, nodeCenter, pathHandles, selectionCorners } from "./scene.js";

const NS = "http://www.w3.org/2000/svg";

export function el(name, attrs = {}) {
  const node = document.createElementNS(NS, name);
  for (const [key, value] of Object.entries(attrs)) {
    if (value !== null && value !== undefined && value !== "") node.setAttribute(key, String(value));
  }
  return node;
}

function matrixAttr(m) {
  return `matrix(${m.join(" ")})`;
}

function shapeElement(node, view) {
  const selected = (view.selection || []).includes(node.id) || node.id === view.selectedId;
  const shapeClass = view.preview ? "drawing-editor__command-shape" : "drawing-editor__shape";
  const group = el("g", {
    class: "drawing-editor__node" + (selected ? " is-selected" : ""),
    transform: matrixAttr(node.transform),
    opacity: node.opacity === 1 ? null : node.opacity,
    "data-node-id": node.id,
  });
  if (node.visible === false) group.setAttribute("data-hidden", "true");
  if (selected) group.setAttribute("data-selected", "true");

  const fill = node.fill || "none";
  const stroke = node.stroke || "none";

  if (node.kind === "polygon") {
    const allVisible = !node.edgeVisible || node.edgeVisible.every(Boolean);
    group.appendChild(
      el("polygon", {
        class: shapeClass,
        points: node.points.map((point) => point.join(",")).join(" "),
        fill,
        stroke: allVisible ? stroke : "none",
        "stroke-width": node.strokeWidth,
        "stroke-linejoin": "miter",
      })
    );
    if (!allVisible) {
      for (const run of visibleRuns(node)) {
        group.appendChild(
          el("polyline", {
            class: shapeClass + " drawing-editor__shape--outline",
            points: run.map((point) => point.join(",")).join(" "),
            fill: "none",
            stroke,
            "stroke-width": node.strokeWidth,
            "stroke-linejoin": "miter",
            "stroke-linecap": "butt",
          })
        );
      }
    }
  } else if (node.kind === "ellipse") {
    group.appendChild(
      el("ellipse", {
        class: shapeClass,
        cx: node.cx,
        cy: node.cy,
        rx: node.rx,
        ry: node.ry,
        fill,
        stroke,
        "stroke-width": node.strokeWidth,
      })
    );
  } else if (node.kind === "path") {
    group.appendChild(
      el("path", {
        class: shapeClass,
        d: node.d,
        fill,
        stroke,
        "stroke-width": node.strokeWidth,
        "stroke-linejoin": "miter",
        "stroke-linecap": "round",
      })
    );
  } else if (node.kind === "group") {
    for (const child of node.nodes) group.appendChild(shapeElement(child, view));
  }
  return group;
}

/** Contiguous runs of visible edges, so a hidden edge leaves a clean break. */
export function visibleRuns(node) {
  const points = node.points;
  const visible = node.edgeVisible || points.map(() => true);
  const runs = [];
  let run = null;
  for (let index = 0; index < points.length; index += 1) {
    if (visible[index] === false) {
      run = null;
      continue;
    }
    if (!run) {
      run = [points[index]];
      runs.push(run);
    }
    run.push(points[(index + 1) % points.length]);
  }
  // The first and last runs join across the wrap-around when that edge is
  // visible; merge them so the outline is one polyline, not two.
  if (runs.length > 1) {
    const first = runs[0];
    const last = runs[runs.length - 1];
    const start = first[0];
    const end = last[last.length - 1];
    if (start[0] === end[0] && start[1] === end[1]) {
      last.push(...first.slice(1));
      runs.shift();
    }
  }
  return runs.filter((item) => item.length > 1);
}

function overlayElements(scene, view) {
  const found = findById(scene.nodes, view.selectedId);
  if (!found) return [];
  // A single selection keeps its oriented box; a
  // multi-selection shares a world-space transform box.
  const node = found;
  const ids = view.selection?.length ? view.selection : [node.id];
  const toView = multiply(view.viewport, nodeFrame(scene, node.id).world);
  const corners = selectionCorners(scene, ids).map(point => apply(view.viewport, point));

  const elements = [
    el("polygon", {
      class: "drawing-editor__selection",
      points: corners.map((point) => point.join(",")).join(" "),
    }),
  ];

  if (view.mode === "transform" && view.tool === "select") {
    corners.forEach((point, index) => {
      elements.push(
        el("rect", {
          class: "drawing-editor__scale-handle",
          x: point[0] - 5,
          y: point[1] - 5,
          width: 10,
          height: 10,
          "data-corner": index,
        })
      );
    });
    const top = [(corners[0][0] + corners[1][0]) / 2, (corners[0][1] + corners[1][1]) / 2];
    const center = [(corners[0][0] + corners[2][0]) / 2, (corners[0][1] + corners[2][1]) / 2];
    const outward = normalize([top[0] - center[0], top[1] - center[1]]);
    const rotate = [top[0] + outward[0] * 28, top[1] + outward[1] * 28];
    elements.push(el("line", { class: "drawing-editor__rotate-stem", x1: top[0], y1: top[1], x2: rotate[0], y2: rotate[1] }));
    elements.push(el("circle", { class: "drawing-editor__rotate-handle", cx: rotate[0], cy: rotate[1], r: 6 }));
    if (ids.length === 1) {
      const pivot = apply(toView, node.pivot || nodeCenter(node));
      elements.push(el("circle", {class:"drawing-editor__handle", cx:pivot[0], cy:pivot[1], r:5, "data-transform-pivot":"true", role:"button", tabindex:0, "aria-label":"Pivot della trasformazione"}));
    }
  }

  if (view.mode === "vertex" && node.kind === "polygon") {
    node.points.forEach((point, index) => {
      const viewPoint = apply(toView, point);
      elements.push(
        el("circle", {
          class: "drawing-editor__handle",
          cx: viewPoint[0],
          cy: viewPoint[1],
          r: 6,
          "data-vertex": index,
        })
      );
      // One toggle per edge, at its midpoint: hide the outline without losing
      // the fill, which is how adjoining body parts avoid a black seam.
      const next = apply(toView, node.points[(index + 1) % node.points.length]);
      const hidden = Boolean(node.edgeVisible) && node.edgeVisible[index] === false;
      elements.push(
        el("rect", {
          class: "drawing-editor__edge-handle" + (hidden ? " is-hidden" : ""),
          x: (viewPoint[0] + next[0]) / 2 - 4,
          y: (viewPoint[1] + next[1]) / 2 - 4,
          width: 8,
          height: 8,
          "data-edge": index,
        })
      );
    });
  }

  if (view.mode === "vertex" && node.kind === "ellipse") {
    const circle = node.constraint?.kind === "circle";
    const handles = [["center", [node.cx, node.cy], "Centro"], ["x", [node.cx + node.rx, node.cy], circle ? "Raggio" : "Raggio orizzontale"], ...(!circle ? [["y", [node.cx, node.cy + node.ry], "Raggio verticale"]] : [])];
    for (const [axis, local, label] of handles) {
      const point = apply(toView, local);
      elements.push(el("circle", { class: "drawing-editor__handle", cx: point[0], cy: point[1], r: 6, "data-ellipse-axis": axis, "aria-label": label, role:"button", tabindex:0 }));
    }
  }

  if (view.mode === "vertex" && node.kind === "path") {
    const handles = pathHandles(node.d);
    for (const handle of handles) {
      const point = apply(toView, handle.point);
      if (handle.control && handle.anchor) {
        const origin = apply(toView, handle.anchor);
        elements.push(el("line", { class: "drawing-editor__rotate-stem", x1: origin[0], y1: origin[1], x2: point[0], y2: point[1] }));
      }
      const active = view.pathPoint === `${handle.command}:${handle.offset}`;
      elements.push(el("circle", { class: (handle.control ? "drawing-editor__curve-control" : "drawing-editor__handle") + (active ? " is-active" : ""), cx: point[0], cy: point[1], r: 6, role: "button", tabindex: 0, "aria-label": handle.label, "data-path-command": handle.command, "data-path-offset": handle.offset }));
    }
  }

  if (view.cut) {
    // The cut is an unbounded line: it is drawn past both ends of the artboard
    // so it reads as a plane, not as a segment with two ends to hit.
    const from = apply(view.viewport, view.cut.from);
    const to = apply(view.viewport, view.cut.to);
    const span = Math.hypot(to[0] - from[0], to[1] - from[1]) || 1;
    const reach = 100000 / span;
    const far = [from[0] - (to[0] - from[0]) * reach, from[1] - (to[1] - from[1]) * reach];
    const beyond = [to[0] + (to[0] - from[0]) * reach, to[1] + (to[1] - from[1]) * reach];
    elements.push(
      el("line", {
        class: "drawing-editor__cut-line",
        x1: far[0],
        y1: far[1],
        x2: beyond[0],
        y2: beyond[1],
      }),
      el("circle", {class: "drawing-editor__cut-handle", cx: from[0], cy: from[1], r: 7, "data-cut-handle": "0", role: "button", tabindex: 0, "aria-label": "Primo punto della linea di taglio"}),
      el("circle", {class: "drawing-editor__cut-handle", cx: to[0], cy: to[1], r: 7, "data-cut-handle": "1", role: "button", tabindex: 0, "aria-label": "Secondo punto della linea di taglio"})
    );
  }

  return elements;
}

function normalize(vector) {
  const length = Math.hypot(vector[0], vector[1]) || 1;
  return [vector[0] / length, vector[1] / length];
}

function findById(nodes, id) {
  for (const node of nodes) {
    if (node.id === id) return node;
    if (node.kind === "group") {
      const nested = findById(node.nodes, id);
      if (nested) return nested;
    }
  }
  return null;
}

export function render(svg, scene, view) {
  const sceneLayer = svg.querySelector("[data-drawing-scene-layer], [data-preview-scene-layer]");
  const overlay = svg.querySelector("[data-drawing-overlay], [data-preview-overlay]");
  const { width, height } = scene.artboard;
  // The artboard is a soft guide: a quarter of it is shown around every edge, so
  // artwork drawn past it stays visible instead of being clipped away.
  svg.setAttribute("viewBox", `${-width / 4} ${-height / 4} ${width * 1.5} ${height * 1.5}`);
  const plate = svg.querySelector(".drawing-editor__plate");
  plate.setAttribute("x", 0);
  plate.setAttribute("y", 0);
  plate.setAttribute("width", width);
  plate.setAttribute("height", height);
  sceneLayer.setAttribute("transform", matrixAttr(view.viewport));
  svg.querySelector(".drawing-editor__grid, .drawing-editor__preview-grid").setAttribute("transform", matrixAttr(view.viewport));
  plate.setAttribute("fill", scene.artboard.background);
  plate.style.fill = scene.artboard.background;
  sceneLayer.replaceChildren(...scene.nodes.map((node) => shapeElement(node, view)));
  overlay.replaceChildren(...overlayElements(scene, view));
  if (view.snap) {
    const point = apply(view.viewport, view.snap);
    overlay.appendChild(el("rect", {class:"drawing-editor__snap", x:point[0] - 7, y:point[1] - 7, width:14, height:14}));
  }
  if (view.marquee) {
    const from = apply(view.viewport,view.marquee.from), to = apply(view.viewport,view.marquee.to);
    overlay.appendChild(el("rect", {class:"drawing-editor__selection", "data-drawing-marquee":"true", x:Math.min(from[0],to[0]), y:Math.min(from[1],to[1]), width:Math.abs(to[0]-from[0]), height:Math.abs(to[1]-from[1])}));
  }
  for (const {axis, value} of view.guides || []) {
    const from = apply(view.viewport, axis === 0 ? [value, -100000] : [-100000, value]);
    const to = apply(view.viewport, axis === 0 ? [value, 100000] : [100000, value]);
    overlay.appendChild(el("line", {class:"drawing-editor__snap", "data-snap-guide":axis, x1:from[0], y1:from[1], x2:to[0], y2:to[1]}));
  }
}
