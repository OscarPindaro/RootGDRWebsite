# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#   "opencv-contrib-python==4.11.0.86", "numpy==1.26.4", "shapely==2.1.2",
#   "pillow==12.0.0", "pydantic==2.12.5", "cairosvg==2.8.2",
# ]
# ///
"""Turn detected colour regions into stroked shapes and interior ink into curves.

Consumes the OpenCV trace, never the manually authored drawings.py coordinates.
"""

import argparse
from pathlib import Path

import cairosvg
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
from shapely.geometry import Polygon as GeometryPolygon

from opencv_trace import Trace
from retained_tacito import build_scene as build_retained_tacito
from scene_svg import svg
from shape_edits import EditPlan, apply_plan
from study_scene import INK, Bezier, Cubic, Ellipse, Point, Polygon, Scene, ShapeStyle

ROOT = Path(__file__).resolve().parent


def fit_polygon(contour: np.ndarray) -> list[Point]:
    perimeter = cv2.arcLength(contour, True)
    tolerance = max(1.0, min(4.0, perimeter * 0.009))
    corners = cv2.approxPolyDP(contour, tolerance, True)[:, 0].astype(float)
    samples = contour[:, 0].astype(float)
    if len(corners) < 3:
        return []
    indices = [int(np.argmin(np.linalg.norm(samples - p, axis=1))) for p in corners]
    lines = []
    for index, start in enumerate(indices):
        end = indices[(index + 1) % len(indices)]
        run = (
            samples[start : end + 1]
            if end > start
            else np.concatenate((samples[start:], samples[: end + 1]))
        )
        vx, vy, x, y = cv2.fitLine(
            run.astype(np.float32), cv2.DIST_HUBER, 0, 0.01, 0.01
        ).ravel()
        # Remove small camera/pen drift from almost-horizontal or vertical edges.
        if abs(vy) < 0.035:
            vx, vy = 1.0, 0.0
        elif abs(vx) < 0.035:
            vx, vy = 0.0, 1.0
        lines.append((np.array([x, y]), np.array([vx, vy])))
    fitted = []
    for index, corner in enumerate(corners):
        p, a = lines[index - 1]
        q, b = lines[index]
        matrix = np.column_stack((a, -b))
        if abs(np.linalg.det(matrix)) > 0.12:
            candidate = p + np.linalg.solve(matrix, q - p)[0] * a
            if np.linalg.norm(candidate - corner) <= tolerance * 2.5:
                corner = candidate
        fitted.append(tuple(round(float(v), 2) for v in corner))
    geometry = GeometryPolygon(fitted)
    reference = GeometryPolygon(corners)
    if (
        not geometry.is_valid
        or geometry.area < 5
        or geometry.hausdorff_distance(reference) > tolerance * 2.5
    ):
        fitted = [tuple(map(float, p)) for p in corners]
    return fitted


def ink_paths(mask: np.ndarray) -> list[np.ndarray]:
    """Follow an 8-connected skeleton between endpoints/junctions, including loops."""
    skeleton = cv2.ximgproc.thinning(mask)
    pixels = set(zip(*np.nonzero(skeleton)))
    neighbors = {}
    for y, x in pixels:
        adjacent = []
        for dy, dx in (
            (-1, 0),
            (1, 0),
            (0, -1),
            (0, 1),
            (-1, -1),
            (-1, 1),
            (1, -1),
            (1, 1),
        ):
            point = (y + dy, x + dx)
            if point not in pixels:
                continue
            if dx and dy and ((y + dy, x) in pixels or (y, x + dx) in pixels):
                continue
            adjacent.append(point)
        neighbors[(y, x)] = adjacent
    visited = set()
    paths = []
    # Branch/end points first; the second pass catches closed loops.
    starts = sorted(p for p in pixels if len(neighbors[p]) != 2) + sorted(pixels)
    for start in starts:
        for following in neighbors[start]:
            edge = frozenset((start, following))
            if edge in visited:
                continue
            visited.add(edge)
            path = [start, following]
            previous, current = start, following
            while len(neighbors[current]) == 2:
                following = next(p for p in neighbors[current] if p != previous)
                edge = frozenset((current, following))
                if edge in visited:
                    break
                visited.add(edge)
                path.append(following)
                previous, current = current, following
            if len(path) >= 7:
                paths.append(np.array([(x, y) for y, x in path], np.float32))
    return paths


def reconstruct(trace: Trace, ink: np.ndarray) -> Scene:
    height, width = trace.height, trace.width
    silhouette = np.zeros((height, width), np.uint8)
    cv2.drawContours(
        silhouette, [np.int32(p) for p in trace.regions[0].loops], -1, 255, cv2.FILLED
    )
    seeds = np.full((height, width), -1, np.int32)
    seeds[silhouette == 0] = 0
    for index, region in enumerate(trace.regions[1:], start=1):
        mask = np.zeros_like(silhouette)
        cv2.drawContours(mask, [np.int32(p) for p in region.loops], -1, 255, cv2.FILLED)
        seeds[mask > 0] = index
    # Allocate ink pixels to the nearest fill/background seed. Shared borders now
    # follow the centre of the ink instead of retaining two ragged ink edges.
    unknown = np.uint8(seeds < 0) * 255
    _, nearest = cv2.distanceTransformWithLabels(
        unknown, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL
    )
    lookup = np.zeros(int(nearest.max()) + 1, np.int32)
    known = seeds >= 0
    lookup[nearest[known]] = seeds[known]
    labels = lookup[nearest]
    scene = Scene(name=trace.name, width=width, height=height, shapes=[])
    for index, region in enumerate(trace.regions[1:], start=1):
        mask = np.uint8(labels == index) * 255
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        smooth = cv2.morphologyEx(
            cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel), cv2.MORPH_OPEN, kernel
        )
        if np.count_nonzero(smooth) < 12:
            smooth = mask
        contours, _ = cv2.findContours(smooth, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        for part, contour in enumerate(
            sorted(contours, key=cv2.contourArea, reverse=True)
        ):
            area = cv2.contourArea(contour)
            if area < 12:
                continue
            style = ShapeStyle(
                id=f"{region.id}-{part}",
                source_region=region.id,
                fill=region.color,
                stroke_width=round(min(6, 1.8 + area**0.5 * 0.16), 2),
            )
            points = fit_polygon(contour)
            if len(points) < 3:
                continue
            # Small rounded marks may be represented as actual ellipses when the
            # fitted ellipse overlaps at least 90% of the detected component.
            if len(points) >= 6 and 30 < area < 400 and len(contour) >= 5:
                ellipse = cv2.fitEllipse(contour)
                candidate, reference = np.zeros_like(mask), np.zeros_like(mask)
                cv2.ellipse(candidate, ellipse, 255, cv2.FILLED)
                cv2.drawContours(reference, [contour], -1, 255, cv2.FILLED)
                union = np.count_nonzero(candidate | reference)
                overlap = np.count_nonzero(candidate & reference) / max(union, 1)
                if overlap > 0.90:
                    center, axes, rotation = ellipse
                    scene.shapes.append(
                        Ellipse(
                            **style.model_dump(),
                            center=center,
                            radii=(axes[0] / 2, axes[1] / 2),
                            rotation=rotation,
                        )
                    )
                    continue
            scene.shapes.append(
                Polygon(**style.model_dump(), kind="polygon", points=points)
            )
    # Outer fills are painted first, then small inset shapes such as eyes.
    scene.shapes.sort(
        key=lambda s: (
            abs(cv2.contourArea(np.float32(s.points)))
            if isinstance(s, Polygon)
            else np.pi * s.radii[0] * s.radii[1]
        ),
        reverse=True,
    )
    boundary = np.zeros_like(silhouette)
    boundary[:-1][labels[:-1] != labels[1:]] = 255
    boundary[:, :-1][labels[:, :-1] != labels[:, 1:]] = 255
    near_boundary = cv2.dilate(
        boundary, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (21, 21))
    )
    painted = np.zeros_like(silhouette)
    for shape in scene.shapes:
        if isinstance(shape, Polygon):
            cv2.fillPoly(painted, [np.int32(shape.points)], 255)
        elif isinstance(shape, Ellipse):
            cv2.ellipse(
                painted,
                (
                    shape.center,
                    (shape.radii[0] * 2, shape.radii[1] * 2),
                    shape.rotation,
                ),
                255,
                cv2.FILLED,
            )
    interior_ink = cv2.bitwise_and(
        ink, cv2.bitwise_and(painted, cv2.bitwise_not(near_boundary))
    )
    interior_ink = cv2.morphologyEx(
        interior_ink,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
    )
    for index, path in enumerate(ink_paths(interior_ink)):
        points = cv2.approxPolyDP(path, 1.2, False)[:, 0].astype(float)
        vx, vy, x, y = cv2.fitLine(path, cv2.DIST_HUBER, 0, 0.01, 0.01).ravel()
        direction, origin = np.array([vx, vy]), np.array([x, y])
        distances = np.abs((path[:, 0] - x) * vy - (path[:, 1] - y) * vx)
        tolerance = max(1.5, cv2.arcLength(path, False) * 0.025)
        if (
            np.quantile(distances, 0.9) < tolerance
            and np.linalg.norm(path[-1] - path[0]) > 2
        ):
            points = np.array(
                [
                    origin + np.dot(p - origin, direction) * direction
                    for p in (path[0], path[-1])
                ]
            )
        if len(points) < 2:
            continue
        style = ShapeStyle(
            id=f"ink-detail-{index}",
            source_region="interior-ink",
            fill="none",
            stroke_width=3,
        )
        if len(points) < 4:
            scene.shapes.append(
                Polygon(**style.model_dump(), kind="polyline", points=points.tolist())
            )
        else:
            segments = []
            for j in range(len(points) - 1):
                p0, p1 = points[max(0, j - 1)], points[j]
                p2, p3 = points[j + 1], points[min(len(points) - 1, j + 2)]
                segments.append(
                    Cubic(
                        control1=tuple(p1 + (p2 - p0) / 6),
                        control2=tuple(p2 - (p3 - p1) / 6),
                        end=tuple(p2),
                    )
                )
            scene.shapes.append(
                Bezier(**style.model_dump(), start=tuple(points[0]), segments=segments)
            )
    return scene


def present(scenes: list[Scene], output: Path, inputs: Path) -> None:
    cards = []
    board = Image.new("RGB", (1710, 2210), "#f4f0e5")
    draw = ImageDraw.Draw(board)
    font = "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf"
    title, small = ImageFont.truetype(font, 30), ImageFont.truetype(font, 18)
    draw.text(
        (30, 25),
        "Dal contorno alle forme · correzioni guidate",
        font=title,
        fill=INK,
    )
    for column, label in enumerate(
        ("Foto raddrizzata", "Prima estrazione OpenCV", "Regolarizzazione / livelli")
    ):
        draw.text((30 + column * 560, 85), label, font=small, fill="#786e61")
    for index, (slug, scene) in enumerate(
        zip(("altus", "luciano", "wolf"), scenes, strict=True)
    ):
        for column, path in enumerate(
            (
                inputs / f"{slug}-rectified.png",
                inputs / f"{slug}-polygons.png",
                output / f"{slug}.png",
            )
        ):
            image = ImageOps.contain(Image.open(path).convert("RGBA"), (510, 600))
            board.paste(
                image,
                (
                    30 + column * 560 + (510 - image.width) // 2,
                    140 + index * 680 + (600 - image.height) // 2,
                ),
                image,
            )
        curves = sum(s.kind == "bezier" for s in scene.shapes)
        draw.text((30, 140 + index * 680 + 620), scene.name, font=title, fill=INK)
        draw.text(
            (1150, 140 + index * 680 + 630),
            f"{len(scene.shapes)} oggetti · {curves} curve",
            font=small,
            fill="#786e61",
        )
        inline = svg(scene).decode()
        trace_label = (
            "Prima estrazione · riferimento preferito"
            if slug == "wolf"
            else "Prima estrazione OpenCV"
        )
        final_label = (
            "Variante a livelli · spada dietro"
            if slug == "wolf"
            else "Forme regolarizzate · seleziona un oggetto"
        )
        cards.append(f"""
        <article><h2>{scene.name}</h2><p>{len(scene.shapes)} oggetti separati · {curves} curve Bézier · {len(scene.anchors)} punti condivisi</p>
        <div class="figures">
        <figure class="reference"><a href="../references/{slug}.jpg" target="_blank">
        <img src="../opencv/{slug}-rectified.png" alt="Fotografia originale di {scene.name}, ritagliata e raddrizzata"></a>
        <figcaption>Foto di riferimento · apri originale</figcaption></figure>
        <figure><img src="../opencv/{slug}-polygons.png" alt="Prima estrazione OpenCV di {scene.name}">
        <figcaption>{trace_label}</figcaption></figure>
        <figure class="interactive">{inline}<figcaption class="selection">{final_label}</figcaption></figure></div>
        <nav><a href="{slug}.svg" download>SVG a forme</a><a href="{slug}.json" download>Scena JSON</a>
        <a href="{slug}-detected.json" download>Prima delle correzioni</a>
        <a href="{slug}-parts.svg" target="_blank">Mappa degli oggetti</a>
        <a href="../opencv/{slug}-contours.svg" target="_blank">Contorni della prima estrazione</a>
        <button type="button" class="explode">Separa gli oggetti</button></nav></article>""")
    board.save(output / "comparison.png")
    preview = Image.new("RGB", (1500, 920), "#f4f0e5")
    ink = ImageDraw.Draw(preview)
    ink.text((30, 25), "OpenCV → forme indipendenti", font=title, fill=INK)
    ink.text(
        (30, 80),
        "Estrazione OpenCV · contorni più marcati · correzioni guidate con punti condivisi",
        font=small,
        fill="#786e61",
    )
    for index, (slug, scene) in enumerate(
        zip(("altus", "luciano", "wolf"), scenes, strict=True)
    ):
        image = ImageOps.contain(Image.open(output / f"{slug}.png"), (440, 680))
        preview.paste(
            image,
            (
                30 + index * 490 + (440 - image.width) // 2,
                130 + (680 - image.height) // 2,
            ),
            image,
        )
        ink.text((30 + index * 490, 835), scene.name, font=title, fill=INK)
        ink.text(
            (30 + index * 490, 880),
            f"{len(scene.shapes)} oggetti separati",
            font=small,
            fill="#786e61",
        )
    preview.save(output / "preview.png")
    (output / "index.html").write_text(
        """<!doctype html><html lang="it"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Ricostruzione a forme</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f4f0e5;color:#302d2b;font:16px/1.6 system-ui}
main{max-width:1560px;margin:auto;padding:30px}h1{font:44px Georgia,serif}h2{font:30px Georgia,serif}
p{max-width:950px}article{border-top:1px solid #c9bfac;padding:20px 0}.figures{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:24px}
figure{margin:0;min-width:0}figure img,figure svg{width:100%;height:570px;object-fit:contain}figcaption{text-align:center}
.reference a{display:block}
svg g{cursor:pointer}svg g:hover>*:not(title),svg g.selected>*:not(title){stroke:#ed843e}
nav{display:flex;gap:24px;flex-wrap:wrap}a,button{color:#365b70;min-height:44px;display:inline-flex;align-items:center}
button{font:inherit;background:transparent;border:1px solid #b8ad97;padding:0 12px;cursor:pointer}
button:focus-visible,a:focus-visible,svg g:focus-visible{outline:3px solid #008ed0;outline-offset:4px}
@media(max-width:650px){main{padding:20px 14px}.figures{grid-template-columns:1fr 1fr;gap:16px 8px}.reference{grid-column:1/-1}figure img,figure svg{height:350px}figcaption{font-size:13px}}
</style><main><p>Root GDR · studio 04</p><h1>Dai contorni alle forme.</h1>
<p>Le regioni rilevate diventano oggetti indipendenti: poligoni con bordi regolari,
piccole ellissi quando riconoscibili e curve Bézier per alcuni dettagli interni.
Puoi selezionare gli oggetti o separarli per vedere la composizione.</p>
<p>La <strong>prima estrazione</strong> segue le regioni di colore e conserva parte
del contorno del pennarello. La ricostruzione a destra raddrizza i bordi e applica
le tue indicazioni: colletto triangolare per Altus, ali geometriche per Luciano.
I punti condivisi tengono unite le forme vicine. Le correzioni sono registrate e ripetibili.</p>
<p>Le piume rosse di Altus sono adattate a triangoli, le facce della lama a trapezi.
Il mantello conserva sette lati e il dettaglio dell’orlo.
Per Tacito manteniamo la prima estrazione come riferimento: la variante a destra
conserva quei contorni e ricostruisce una spada completa, disegnata dietro il corpo.
Le parti nascoste della spada sono un’interpretazione guidata.</p>
<nav><a href="comparison.png" target="_blank">Confronto PNG completo</a>
<a href="../study.zip" download>Scarica SVG, JSON e codice</a>
<a href="../pose-comparison/">Confronto dei modelli di posa</a></nav>
<p><a href="../generated/">Corpo continuo da scheletro e bisettrici</a></p>
CARDS
</main><script>
for (const figure of document.querySelectorAll('.interactive')) {
  const svg = figure.querySelector('svg');
  const select = event => {
    const group = event.target.closest('g');
    if (!group) return;
    svg.querySelectorAll('.selected').forEach(node => node.classList.remove('selected'));
    group.classList.add('selected');
    const kinds = {polygon:'poligono',polyline:'linea',ellipse:'ellisse',bezier:'curva Bézier',compound:'contorni conservati'};
    figure.querySelector('.selection').textContent = group.dataset.label + ' · ' + kinds[group.dataset.kind];
  };
  svg.addEventListener('click', select);
  svg.addEventListener('keydown', event => {if (event.key === 'Enter') select(event)});
}
for (const button of document.querySelectorAll('.explode')) {
  button.addEventListener('click', () => {
    const svg = button.closest('article').querySelector('svg');
    const separated = button.getAttribute('aria-pressed') !== 'true';
    button.setAttribute('aria-pressed', String(separated));
    button.textContent = separated ? 'Ricomponi' : 'Separa gli oggetti';
    svg.dataset.baseViewBox ||= svg.getAttribute('viewBox');
    const [x, y, width, height] = svg.dataset.baseViewBox.split(' ').map(Number);
    svg.setAttribute('viewBox', separated ? `-60 -60 ${width+120} ${height+120}` : svg.dataset.baseViewBox);
    for (const group of svg.querySelectorAll('g')) {
      const bounds = group.getBBox();
      const dx = bounds.x + bounds.width/2 - width/2;
      const dy = bounds.y + bounds.height/2 - height/2;
      const distance = Math.max(1, Math.hypot(dx, dy));
      group.setAttribute('transform', separated ? `translate(${dx/distance*45} ${dy/distance*45})` : '');
    }
  });
}
</script></html>""".replace("CARDS", "".join(cards))
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "output/opencv")
    parser.add_argument("--output", type=Path, default=ROOT / "output/shapes")
    parser.add_argument("--edits", type=Path, default=ROOT / "edits")
    parser.add_argument("--no-edits", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    scenes = []
    for slug in ("altus", "luciano", "wolf"):
        trace = Trace.model_validate_json(
            (args.input / f"{slug}-contours.json").read_text()
        )
        ink = cv2.imread(str(args.input / f"{slug}-ink.png"), cv2.IMREAD_GRAYSCALE)
        scene = reconstruct(trace, ink)
        (args.output / f"{slug}-detected.json").write_text(
            scene.model_dump_json(indent=2) + "\n"
        )
        if not args.no_edits:
            for plan_path in (
                args.edits / "outline.json",
                args.edits / f"{slug}.json",
                args.edits / f"{slug}-regularize.json",
            ):
                if plan_path.exists():
                    scene = apply_plan(
                        scene, EditPlan.model_validate_json(plan_path.read_text())
                    )
            if slug == "wolf":
                (args.output / "wolf-postprocessed.json").write_text(
                    scene.model_dump_json(indent=2) + "\n"
                )
                (args.output / "wolf-postprocessed.svg").write_bytes(svg(scene))
                scene = build_retained_tacito(trace)
        scenes.append(scene)
        (args.output / f"{slug}.json").write_text(scene.model_dump_json(indent=2))
        data = svg(scene)
        (args.output / f"{slug}.svg").write_bytes(data)
        (args.output / f"{slug}-parts.svg").write_bytes(svg(scene, parts=True))
        cairosvg.svg2png(
            bytestring=data,
            write_to=str(args.output / f"{slug}.png"),
            output_height=1400,
        )
        print(f"{slug}: {len(scene.shapes)} independent shapes", flush=True)
    present(scenes, args.output, args.input)


if __name__ == "__main__":
    main()
