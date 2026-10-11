/* The annotation surface: draw coloured marks on a captured screenshot.

   Shapes are kept in the image's own pixel space, so the canvas can be scaled
   to the dialog without moving a mark. The export is the canvas itself, which
   is why a blur is painted by re-drawing the image inside the clip rather than
   kept as a separate layer. */

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

export function createAnnotator(canvas) {
  let image = null;
  let shapes = [];
  let draft = null;
  let tool = "arrow";
  let colour = COLOURS[0];
  let text = "";

  function strokeWidth() {
    return Math.max(2, canvas.width / 360);
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
      context.font = FONT.replace("%d", String(Math.max(16, canvas.width / 42)));
      context.textBaseline = "top";
      context.fillText(shape.text, shape.x, shape.y);
    } else if (shape.tool === "blur") {
      context.beginPath();
      context.rect(shape.x, shape.y, shape.w, shape.h);
      context.clip();
      context.filter = "blur(10px)";
      context.drawImage(image, 0, 0);
    }
    context.restore();
  }

  function render() {
    const context = canvas.getContext("2d");
    context.clearRect(0, 0, canvas.width, canvas.height);
    if (image === null) return;
    context.drawImage(image, 0, 0);
    for (const shape of shapes) paint(context, shape);
    if (draft !== null) paint(context, draft);
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
    if (tool === "text") {
      if (text.trim() === "") return;
      shapes.push({ tool: "text", colour, x: point.x, y: point.y, text: text.trim() });
      render();
      return;
    }
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
    if (Math.abs(draft.w) > MIN_DRAG || Math.abs(draft.h) > MIN_DRAG) {
      shapes.push(draft);
    }
    draft = null;
    render();
  });

  return {
    async load(url) {
      const blob = await (await fetch(url, { headers: { Accept: "image/png" } })).blob();
      const bitmap = await createImageBitmap(blob);
      image = bitmap;
      canvas.width = bitmap.width;
      canvas.height = bitmap.height;
      shapes = [];
      draft = null;
      render();
    },
    setTool(next) {
      tool = next;
    },
    setColour(next) {
      colour = next;
    },
    setText(next) {
      text = next;
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
