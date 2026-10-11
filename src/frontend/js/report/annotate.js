/* The annotation surface: draw coloured marks on a captured screenshot.

   Shapes are kept in the image's own pixel space, so the canvas can be scaled
   to the dialog without moving a mark. The export is the canvas itself, which
   is why a blur is painted by re-drawing the image inside the clip rather than
   kept as a separate layer.

   Text is placed the way a drawing tool does it: the tool drags out an area,
   the reader types into it, and the area goes away. What stays is a note: the
   text wraps at the width that was dragged, and grows downward from there. */

export const COLOURS = [
  "#d1402a",
  "#d97a26",
  "#e0a327",
  "#3c7a52",
  "#3f7fb0",
  "#17150f",
];

const FONT = "600 %dpx system-ui, -apple-system, Segoe UI, sans-serif";
const MIN_DRAG = 4;
// The text is a note, not a stretched shape: its size comes from the capture it
// is written on, and the area the reader drags decides where it wraps.
const TEXT_SCALE = 0.022;
const LINE_HEIGHT = 1.25;
const MIN_FONT = 14;
const MIN_ZOOM = 0.2;
const MAX_ZOOM = 4;

export function createAnnotator(canvas) {
  let image = null;
  let shapes = [];
  let draft = null;
  let tool = "arrow";
  let colour = COLOURS[0];
  let zoom = 1;
  let onTextBox = null;

  /* The canvas keeps the image's own pixel size; the zoom is its CSS size, so
     the marks never move and the pointer mapping keeps dividing by the rect. */
  function applyZoom(next) {
    zoom = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, next));
    canvas.style.width = canvas.width * zoom + "px";
    canvas.style.height = canvas.height * zoom + "px";
    return zoom;
  }

  function strokeWidth() {
    return Math.max(2, canvas.width / 360);
  }

  function textSize() {
    return Math.max(MIN_FONT, canvas.width * TEXT_SCALE);
  }

  /* The dragged area is a width to wrap at, so the note breaks lines the way a
     text box in a drawing tool does. */
  function wrapText(context, value, wrap) {
    const words = value.split(/\s+/).filter(Boolean);
    const lines = [];
    let line = "";
    for (const word of words) {
      const candidate = line ? line + " " + word : word;
      if (line && context.measureText(candidate).width > wrap) {
        lines.push(line);
        line = word;
      } else {
        line = candidate;
      }
    }
    if (line) lines.push(line);
    return lines.length ? lines : [value];
  }

  function normalise(box) {
    return {
      x: box.w < 0 ? box.x + box.w : box.x,
      y: box.h < 0 ? box.y + box.h : box.y,
      w: Math.abs(box.w),
      h: Math.abs(box.h),
    };
  }

  function paint(context, shape) {
    context.save();
    context.strokeStyle = shape.colour;
    context.fillStyle = shape.colour;
    context.lineWidth = strokeWidth();
    context.lineCap = "round";
    context.lineJoin = "round";
    if (shape.tool === "box") {
      context.strokeRect(shape.x, shape.y, shape.w, shape.h);
    } else if (shape.tool === "arrow") {
      const x2 = shape.x + shape.w;
      const y2 = shape.y + shape.h;
      const angle = Math.atan2(shape.h, shape.w);
      const head = strokeWidth() * 4;
      context.beginPath();
      context.moveTo(shape.x, shape.y);
      context.lineTo(x2, y2);
      context.moveTo(x2, y2);
      context.lineTo(
        x2 - head * Math.cos(angle - Math.PI / 7),
        y2 - head * Math.sin(angle - Math.PI / 7)
      );
      context.moveTo(x2, y2);
      context.lineTo(
        x2 - head * Math.cos(angle + Math.PI / 7),
        y2 - head * Math.sin(angle + Math.PI / 7)
      );
      context.stroke();
    } else if (shape.tool === "text") {
      context.font = FONT.replace("%d", String(shape.size));
      context.textBaseline = "top";
      const lineHeight = shape.size * LINE_HEIGHT;
      wrapText(context, shape.text, shape.wrap).forEach((line, index) => {
        context.fillText(line, shape.x, shape.y + index * lineHeight);
      });
    } else if (shape.tool === "blur") {
      context.beginPath();
      context.rect(shape.x, shape.y, shape.w, shape.h);
      context.clip();
      context.filter = "blur(10px)";
      context.drawImage(image, 0, 0);
    }
    context.restore();
  }

  /* The box being dragged out for a text is a selection, not a mark: it is
     dashed while the reader sizes it and gone once the text is placed. */
  function paintSelection(context, box) {
    const area = normalise(box);
    context.save();
    context.strokeStyle = colour;
    context.lineWidth = strokeWidth();
    context.setLineDash([strokeWidth() * 3, strokeWidth() * 3]);
    context.strokeRect(area.x, area.y, area.w, area.h);
    context.restore();
  }

  function render() {
    const context = canvas.getContext("2d");
    context.clearRect(0, 0, canvas.width, canvas.height);
    if (image === null) return;
    context.drawImage(image, 0, 0);
    for (const shape of shapes) paint(context, shape);
    if (draft === null) return;
    if (draft.tool === "text") paintSelection(context, draft);
    else paint(context, draft);
  }

  function toImage(event) {
    const rect = canvas.getBoundingClientRect();
    return {
      x: (event.clientX - rect.left) * (canvas.width / rect.width),
      y: (event.clientY - rect.top) * (canvas.height / rect.height),
    };
  }

  canvas.addEventListener("pointerdown", (event) => {
    if (image === null) return;
    canvas.setPointerCapture(event.pointerId);
    const point = toImage(event);
    draft = { tool, colour, x: point.x, y: point.y, w: 0, h: 0 };
  });

  canvas.addEventListener("pointermove", (event) => {
    if (draft === null) return;
    const point = toImage(event);
    draft.w = point.x - draft.x;
    draft.h = point.y - draft.y;
    render();
  });

  canvas.addEventListener("pointerup", () => {
    if (draft === null) return;
    const pending = draft;
    draft = null;
    render();
    const area = normalise(pending);
    if (pending.tool === "text") {
      // Only the width matters: it is where the note wraps.
      if (area.w < MIN_DRAG || !onTextBox) return;
      onTextBox(area, {
        x: area.x * zoom,
        y: area.y * zoom,
        w: area.w * zoom,
        h: area.h * zoom,
        fontSize: textSize() * zoom,
      });
      return;
    }
    if (area.w < MIN_DRAG || area.h < MIN_DRAG) return;
    // An arrow keeps the direction it was drawn in; the other marks do not.
    shapes.push(pending.tool === "arrow" ? pending : { ...area, tool: pending.tool, colour: pending.colour });
    render();
  });

  canvas.addEventListener(
    "wheel",
    (event) => {
      if (!event.ctrlKey || image === null) return;
      event.preventDefault();
      applyZoom(zoom * (event.deltaY < 0 ? 1.1 : 0.9));
      canvas.dispatchEvent(new CustomEvent("report:zoom", { detail: zoom }));
    },
    { passive: false }
  );

  return {
    async load(url) {
      const blob = await (await fetch(url, { headers: { Accept: "image/png" } })).blob();
      const bitmap = await createImageBitmap(blob);
      image = bitmap;
      canvas.width = bitmap.width;
      canvas.height = bitmap.height;
      shapes = [];
      draft = null;
      applyZoom(1);
      render();
      // A canvas is 300×150 until something sets it, so "loaded" needs saying.
      canvas.dataset.reportLoaded = "true";
    },
    fit(available) {
      if (image === null || !available) return applyZoom(1);
      return applyZoom(Math.min(1, available / canvas.width));
    },
    zoomBy(factor) {
      return applyZoom(zoom * factor);
    },
    setTool(next) {
      tool = next;
    },
    setColour(next) {
      colour = next;
    },
    setTextBoxHandler(handler) {
      onTextBox = handler;
    },
    placeText(box, value) {
      const text = (value || "").trim();
      if (text === "") return false;
      shapes.push({
        tool: "text",
        colour,
        x: box.x,
        y: box.y,
        size: textSize(),
        wrap: Math.max(MIN_DRAG, box.w),
        text,
      });
      render();
      return true;
    },
    undo() {
      shapes.pop();
      render();
    },
    toBlob() {
      return new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
    },
  };
}
