"""Pixel comparison of two screenshots and the side-by-side HTML report.

The diff runs in Chromium — the same browser that took the screenshots — so no
image library is needed: both PNGs are loaded into a canvas and compared pixel
by pixel. The report is the primary artefact; the numbers are a secondary
signal, not a gate.
"""

from __future__ import annotations

import base64
from pathlib import Path

from playwright.sync_api import sync_playwright
from pydantic import BaseModel

_DIFF_JS = """
async ({ a, b, threshold }) => {
  const load = (src) => new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = reject;
    image.src = src;
  });
  const [imageA, imageB] = await Promise.all([load(a), load(b)]);
  const width = Math.min(imageA.width, imageB.width);
  const height = Math.min(imageA.height, imageB.height);
  const canvasA = document.createElement("canvas");
  canvasA.width = width;
  canvasA.height = height;
  const canvasB = document.createElement("canvas");
  canvasB.width = width;
  canvasB.height = height;
  const contextA = canvasA.getContext("2d");
  const contextB = canvasB.getContext("2d");
  contextA.drawImage(imageA, 0, 0);
  contextB.drawImage(imageB, 0, 0);
  const dataA = contextA.getImageData(0, 0, width, height).data;
  const dataB = contextB.getImageData(0, 0, width, height).data;
  const out = document.createElement("canvas");
  out.width = width;
  out.height = height;
  const contextOut = out.getContext("2d");
  const imageOut = contextOut.createImageData(width, height);
  let differing = 0;
  let minX = width;
  let minY = height;
  let maxX = -1;
  let maxY = -1;
  for (let index = 0; index < dataA.length; index += 4) {
    const delta =
      Math.abs(dataA[index] - dataB[index]) +
      Math.abs(dataA[index + 1] - dataB[index + 1]) +
      Math.abs(dataA[index + 2] - dataB[index + 2]);
    const pixel = index / 4;
    const x = pixel % width;
    const y = (pixel - x) / width;
    if (delta > threshold) {
      differing += 1;
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
      imageOut.data[index] = 255;
      imageOut.data[index + 1] = 0;
      imageOut.data[index + 2] = 0;
      imageOut.data[index + 3] = 255;
    } else {
      imageOut.data[index] = dataA[index];
      imageOut.data[index + 1] = dataA[index + 1];
      imageOut.data[index + 2] = dataA[index + 2];
      imageOut.data[index + 3] = 48;
    }
  }
  contextOut.putImageData(imageOut, 0, 0);
  return {
    width,
    height,
    differing,
    total: width * height,
    box: maxX >= 0 ? [minX, minY, maxX, maxY] : null,
    diffPng: out.toDataURL("image/png"),
  };
}
"""


class PixelDiff(BaseModel):
    """How much two screenshots differ."""

    width: int
    height: int
    differing: int
    total: int
    percent: float
    box: tuple[int, int, int, int] | None


class Comparison(BaseModel):
    """One viewport's app / prototype / diff screenshots."""

    viewport: str
    app: str
    prototype: str
    diff: str
    stats: PixelDiff


def _data_url(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def pixel_diff(
    app_png: Path, prototype_png: Path, output: Path, *, threshold: int = 32
) -> PixelDiff:
    """Compare two PNGs and write the difference image to ``output``."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            result = page.evaluate(
                _DIFF_JS,
                {
                    "a": _data_url(app_png),
                    "b": _data_url(prototype_png),
                    "threshold": threshold,
                },
            )
        finally:
            browser.close()

    payload = result["diffPng"].split(",", 1)[1]
    output.write_bytes(base64.b64decode(payload))
    total = int(result["total"])
    return PixelDiff(
        width=int(result["width"]),
        height=int(result["height"]),
        differing=int(result["differing"]),
        total=total,
        percent=round(result["differing"] / total * 100, 2) if total else 0.0,
        box=tuple(result["box"]) if result["box"] else None,
    )


def write_report(directory: Path, *, title: str, comparisons: list[Comparison]) -> Path:
    """Write ``report.html`` with the screenshots side by side, per viewport."""
    rows = []
    for comparison in comparisons:
        stats = comparison.stats
        box = f"{stats.box}" if stats.box else "—"
        rows.append(
            f"""
    <section>
      <h2>{comparison.viewport} — {stats.percent}% differing ({box})</h2>
      <div class="row">
        <figure><figcaption>App</figcaption>
          <img src="{comparison.app}" alt="app {comparison.viewport}"></figure>
        <figure><figcaption>Prototype</figcaption>
          <img src="{comparison.prototype}" alt="prototype {comparison.viewport}"></figure>
        <figure><figcaption>Diff</figcaption>
          <img src="{comparison.diff}" alt="diff {comparison.viewport}"></figure>
      </div>
    </section>"""
        )

    report = directory / "report.html"
    report.write_text(
        f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  body {{ font: 14px/1.5 system-ui, sans-serif; margin: 1.5rem; background: #f5f3ee; }}
  h1 {{ font-size: 1.4rem; }}
  h2 {{ font-size: 1rem; margin: 1.5rem 0 .5rem; }}
  .row {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; }}
  figure {{ margin: 0; }}
  figcaption {{ font-size: .75rem; text-transform: uppercase; letter-spacing: .08em;
    color: #666; margin-bottom: .3rem; }}
  img {{ width: 100%; border: 1px solid #ccc; background: #fff; }}
</style>
</head>
<body>
<h1>{title}</h1>
{"".join(rows)}
</body>
</html>
""",
        encoding="utf-8",
    )
    return report
