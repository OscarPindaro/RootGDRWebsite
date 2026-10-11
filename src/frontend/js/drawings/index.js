/* Entry point for the drawing editor bundle.

   Loaded on demand by `editorial/DrawingEditor.js`, which the component
   declares: a reading page never downloads it. It mounts one controller per
   workspace and re-checks after an htmx swap. */

import { createController } from "./controller.js";

function mount(root) {
  if (root.dataset.drawingMounted === "true") return;
  root.dataset.drawingMounted = "true";
  const controller = createController(root);
  root.__drawingEditor = controller;
  controller.mount();
}

function mountAll() {
  document.querySelectorAll("[data-drawing-editor]").forEach(mount);
}

mountAll();
document.body.addEventListener("htmx:afterSwap", mountAll);
