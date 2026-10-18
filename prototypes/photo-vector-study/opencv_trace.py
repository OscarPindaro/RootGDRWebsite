# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#   "opencv-python-headless==4.11.0.86", "numpy==1.26.4",
#   "pillow==12.0.0", "pydantic==2.12.5", "cairosvg==2.8.2",
# ]
# ///
"""Automatic tracing of outlined drawings on light paper.

No coordinates, colours, crops or shapes from drawings.py are used.
The same thresholds and morphology are applied to all three photographs.
"""

import argparse
from html import escape
from pathlib import Path
import xml.etree.ElementTree as ET

import cairosvg
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent
NAMES = [("altus", "Altus"), ("luciano", "Luciano"), ("wolf", "Tacito")]
PAPER = "#f4f0e5"


class Region(BaseModel):
    id: str
    color: str
    pixel_area: int
    # Each loop is a closed contour. Even-odd filling preserves holes.
    loops: list[list[tuple[int, int]]]


class Trace(BaseModel):
    name: str
    width: int
    height: int
    paper_corners: list[tuple[float, float]]
    crop_on_rectified_paper: tuple[int, int, int, int]
    algorithm: str = (
        "HSV ink mask, connected regions, contour extraction, Douglas-Peucker"
    )
    epsilon_pixels: float
    regions: list[Region]


def rectify(photo: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Find the largest light, low-saturation quadrilateral and rectify it."""
    hsv = cv2.cvtColor(photo, cv2.COLOR_BGR2HSV)
    paper = np.uint8((hsv[:, :, 1] < 100) & (hsv[:, :, 2] > 140)) * 255
    paper = cv2.morphologyEx(paper, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    contours, _ = cv2.findContours(paper, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = sorted(contours, key=cv2.contourArea, reverse=True)
    corners = None
    for contour in candidates[:5]:
        if cv2.contourArea(contour) < photo.shape[0] * photo.shape[1] * 0.15:
            continue
        for fraction in (0.015, 0.025, 0.04):
            approx = cv2.approxPolyDP(
                contour, fraction * cv2.arcLength(contour, True), True
            )
            if len(approx) == 4 and cv2.isContourConvex(approx):
                corners = approx[:, 0, :].astype(np.float32)
                break
        if corners is not None:
            break
    if corners is None:
        raise ValueError(
            "No large paper quadrilateral detected; no manual fallback was applied."
        )
    sums = corners.sum(axis=1)
    differences = np.diff(corners, axis=1).ravel()
    ordered = np.array(
        [
            corners[np.argmin(sums)],
            corners[np.argmin(differences)],
            corners[np.argmax(sums)],
            corners[np.argmax(differences)],
        ]
    )
    if len(np.unique(ordered, axis=0)) != 4:
        raise ValueError("Ambiguous paper corner ordering.")
    tl, tr, br, bl = ordered
    width = round(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl)))
    height = round(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr)))
    destination = np.float32(
        [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]]
    )
    transform = cv2.getPerspectiveTransform(ordered, destination)
    return cv2.warpPerspective(photo, transform, (width, height)), ordered, transform


def extract(
    photo: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, tuple[int, int, int, int]]:
    """Keep the main connected drawing and separate fills at the dark outlines."""
    smooth = cv2.bilateralFilter(photo, 7, 45, 45)
    hsv = cv2.cvtColor(smooth, cv2.COLOR_BGR2HSV)
    saturation, value = hsv[:, :, 1], hsv[:, :, 2]
    # Coloured pencil/marker areas or dark outlines, excluding the paper.
    foreground = np.uint8((saturation > 80) | (value < 155)) * 255
    foreground[:12] = foreground[-12:] = 0
    foreground[:, :12] = foreground[:, -12:] = 0
    foreground = cv2.morphologyEx(
        foreground, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8)
    )
    count, labels, stats, _ = cv2.connectedComponentsWithStats(foreground)
    if count < 2:
        raise ValueError("No foreground drawing detected.")
    main = int(np.argmax(stats[1:, cv2.CC_STAT_AREA])) + 1
    mask = np.uint8(labels == main) * 255
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    silhouette = np.zeros_like(mask)
    cv2.drawContours(silhouette, contours, -1, 255, cv2.FILLED)
    x, y, width, height = cv2.boundingRect(silhouette)
    x0, y0 = max(0, x - 15), max(0, y - 15)
    x1, y1 = min(photo.shape[1], x + width + 15), min(photo.shape[0], y + height + 15)
    # Saturation prevents dark purple/blue fill from becoming black ink.
    ink = np.uint8(((value < 110) & (saturation < 115)) | (value < 65)) * 255
    ink = cv2.morphologyEx(
        ink, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    )
    return (
        smooth[y0:y1, x0:x1],
        silhouette[y0:y1, x0:x1],
        ink[y0:y1, x0:x1],
        (x0, y0, x1, y1),
    )


def regions(
    image: np.ndarray, silhouette: np.ndarray, ink: np.ndarray, epsilon: float
) -> list[Region]:
    """Trace a dark silhouette, then each connected non-ink region above it."""
    fills = cv2.bitwise_and(silhouette, cv2.bitwise_not(ink))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(fills)
    masks = [("ink-silhouette", silhouette, int(np.count_nonzero(silhouette)))]
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV).astype(float)
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area < 12:
            continue
        mask = np.uint8(labels == label) * 255
        color = np.median(image[mask > 0], axis=0).astype(np.uint8)
        reference = cv2.cvtColor(color.reshape(1, 1, 3), cv2.COLOR_BGR2HSV)[0, 0]
        hue_delta = np.abs(hsv[:, :, 0] - float(reference[0]))
        hue_delta = np.minimum(hue_delta, 180 - hue_delta)
        # A gap in an ink line can join different fills (e.g. a green buckle and
        # red trousers). Split only strong chromatic differences, not paper texture.
        different = (hsv[:, :, 1] > 100) & (
            ((hue_delta > 18) & (reference[1] > 90)) | (reference[1] < 65)
        )
        different |= (reference[1] > 90) & (hsv[:, :, 1] < 65) & (hsv[:, :, 2] > 170)
        secondary = np.uint8(different & (mask > 0)) * 255
        subcount, sublabels, substats, _ = cv2.connectedComponentsWithStats(secondary)
        for sublabel in range(1, subcount):
            subarea = int(substats[sublabel, cv2.CC_STAT_AREA])
            if subarea >= 18:
                submask = np.uint8(sublabels == sublabel) * 255
                mask[submask > 0] = 0
                masks.append((f"region-{label:03}-color-{sublabel}", submask, subarea))
        if np.count_nonzero(mask) >= 12:
            masks.append((f"region-{label:03}", mask, int(np.count_nonzero(mask))))
    result = []
    palette: list[tuple[np.ndarray, str]] = []
    for name, mask, area in masks:
        samples = cv2.erode(mask, np.ones((3, 3), np.uint8))
        if np.count_nonzero(samples) < 8:
            samples = mask
        if name == "ink-silhouette":
            samples = cv2.bitwise_and(ink, silhouette)
        color = np.median(image[samples > 0], axis=0).astype(np.uint8)
        lab = cv2.cvtColor(color.reshape(1, 1, 3), cv2.COLOR_BGR2LAB)[0, 0].astype(
            float
        )
        hex_color = "#" + "".join(f"{int(c):02x}" for c in color[::-1])
        # Merge near-identical measured fills; there is no hand-selected palette.
        closest = min(
            palette, key=lambda item: np.linalg.norm(item[0] - lab), default=None
        )
        if closest is not None and np.linalg.norm(closest[0] - lab) < 16:
            hex_color = closest[1]
        else:
            palette.append((lab, hex_color))
        contours, _ = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        loops = []
        for contour in contours:
            if abs(cv2.contourArea(contour)) < 5:
                continue
            # Small features need a smaller tolerance than a body silhouette.
            tolerance = min(epsilon, 0.015 * cv2.arcLength(contour, True))
            approximate = cv2.approxPolyDP(contour, tolerance, True)
            points = [(int(p[0][0]), int(p[0][1])) for p in approximate]
            if len(points) >= 3 and abs(cv2.contourArea(approximate)) > 0:
                loops.append(points)
        if loops:
            result.append(
                Region(id=name, color=hex_color, pixel_area=area, loops=loops)
            )
    return result


def render(trace: Trace, output: Path, stem: str) -> None:
    root = ET.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "width": str(trace.width),
            "height": str(trace.height),
            "viewBox": f"0 0 {trace.width} {trace.height}",
            "role": "img",
            "aria-labelledby": "title",
        },
    )
    ET.SubElement(root, "title", id="title").text = f"{trace.name} — OpenCV"
    ET.SubElement(
        root, "desc"
    ).text = "Automatically detected image regions. No semantic body parts or skeleton inferred."
    for region in trace.regions:
        group = ET.SubElement(root, "g", id=region.id)
        ET.SubElement(group, "title").text = region.id
        commands = []
        for loop in region.loops:
            commands.append("M " + " L ".join(f"{x},{y}" for x, y in loop) + " Z")
        ET.SubElement(
            group,
            "path",
            {
                "d": " ".join(commands),
                "fill": region.color,
                "fill-rule": "evenodd",
            },
        )
    ET.indent(root)
    data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    (output / f"{stem}.svg").write_bytes(data)
    (output / f"{stem}.json").write_text(trace.model_dump_json(indent=2))
    cairosvg.svg2png(
        bytestring=data, write_to=str(output / f"{stem}.png"), output_height=1400
    )


def comparison(output: Path, traces: list[Trace]) -> None:
    board = Image.new("RGB", (1710, 2210), PAPER)
    draw = ImageDraw.Draw(board)
    font = "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf"
    title = ImageFont.truetype(font, 32)
    small = ImageFont.truetype(font, 20)
    draw.text(
        (35, 25),
        "OpenCV · regioni rilevate dalle fotografie",
        font=title,
        fill="#302d2b",
    )
    for index, label in enumerate(
        ("Foto raddrizzata", "Contorni · max 0,8 px", "Poligoni · max 3 px")
    ):
        draw.text((35 + index * 560, 90), label, font=small, fill="#786e61")
    for row, ((slug, name), trace) in enumerate(zip(NAMES, traces, strict=True)):
        y0 = 145 + row * 680
        for column, suffix in enumerate(("rectified", "contours", "polygons")):
            image = Image.open(output / f"{slug}-{suffix}.png").convert("RGBA")
            image = ImageOps.contain(image, (510, 600))
            board.paste(
                image,
                (
                    35 + column * 560 + (510 - image.width) // 2,
                    y0 + (600 - image.height) // 2,
                ),
                image,
            )
        draw.text((35, y0 + 620), name, font=title, fill="#302d2b")
        vertices = sum(len(loop) for r in trace.regions for loop in r.loops)
        draw.text(
            (595, y0 + 630),
            f"{len(trace.regions) - 1} regioni di riempimento + sagoma d’inchiostro",
            font=small,
            fill="#786e61",
        )
        draw.text(
            (1155, y0 + 630), f"{vertices} vertici totali", font=small, fill="#786e61"
        )
    board.save(output / "comparison.png")
    preview = Image.new("RGB", (1500, 920), PAPER)
    draw = ImageDraw.Draw(preview)
    draw.text(
        (35, 25),
        "OpenCV · poligoni estratti automaticamente",
        font=title,
        fill="#302d2b",
    )
    draw.text(
        (35, 80),
        "Stessi parametri per tutte le foto · nessun vertice disegnato a mano",
        font=small,
        fill="#786e61",
    )
    for index, ((slug, name), trace) in enumerate(zip(NAMES, traces, strict=True)):
        image = Image.open(output / f"{slug}-polygons.png")
        image = ImageOps.contain(image, (440, 680))
        preview.paste(
            image,
            (
                35 + index * 490 + (440 - image.width) // 2,
                130 + (680 - image.height) // 2,
            ),
            image,
        )
        draw.text((35 + index * 490, 835), name, font=title, fill="#302d2b")
        draw.text(
            (35 + index * 490, 880),
            f"{len(trace.regions) - 1} regioni + inchiostro",
            font=small,
            fill="#786e61",
        )
    preview.save(output / "preview.png")


def gallery(output: Path, traces: list[Trace]) -> None:
    rows = []
    for (slug, name), trace in zip(NAMES, traces, strict=True):
        figures = "".join(
            f'<figure><img src="{slug}-{suffix}.png" alt="{escape(name)}: {label}">'
            f"<figcaption>{label}</figcaption></figure>"
            for suffix, label in (
                ("rectified", "Foto raddrizzata"),
                ("contours", "Contorni fedeli · max 0,8 px"),
                ("polygons", "Poligoni semplificati · max 3 px"),
            )
        )
        rows.append(f"""
        <article><h2>{name}</h2>
        <p>{len(trace.regions) - 1} regioni di riempimento + sagoma d’inchiostro</p>
        <div class="figures">{figures}</div>
        <nav><a href="{slug}-contours.svg" download>SVG dei contorni</a>
        <a href="{slug}-polygons.svg" download>SVG semplificato</a>
        <a href="{slug}-polygons.json" download>Coordinate JSON</a>
        <a href="{slug}-detection.png" target="_blank">Rilevamento del foglio</a>
        <a href="{slug}-regions.png" target="_blank">Mappa delle regioni</a></nav></article>""")
    pose = ""
    if (output / "wolf-pose-padded-0.25.png").exists():
        pose = """
        <article><h2>La posa di Tacito</h2>
        <p>Con soglie standard, nessun rilevamento. Con soglie 0,25 e un margine
        aggiunto alla foto isolata, MediaPipe restituisce questa posa:
        testa e parte superiore del corpo finiscono all’altezza dei pantaloni.
        Il risultato non è utilizzabile per animare il personaggio.</p>
        <div class="figures"><figure>
        <img src="wolf-pose-padded-0.25.png" alt="Posa errata rilevata su Tacito">
        <figcaption>Tentativo automatico, da scartare</figcaption></figure>
        <figure><img src="wolf-pose-human-control-0.5.png"
        alt="Posa corretta sulla fotografia di controllo">
        <figcaption>Controllo su una fotografia umana</figcaption></figure></div>
        <p><a href="pose-results.json" download>Risultati della verifica</a></p>
        </article>"""
    (output / "index.html").write_text(
        """<!doctype html>
<html lang="it"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Studio OpenCV · dalle foto ai contorni</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f4f0e5;color:#302d2b;font:16px/1.6 system-ui}
main{max-width:1500px;margin:auto;padding:30px}
h1{font:46px/1.15 Georgia,serif}h2{font:30px Georgia,serif;margin-bottom:0}
.intro{max-width:900px;color:#706557}article{border-top:1px solid #c9bfac;padding:16px 0 28px}
article p{color:#706557}a{color:#365b70;display:inline-flex;align-items:center;min-height:44px}
a:focus-visible{outline:3px solid #008ed0;outline-offset:4px}
.figures{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}
figure{margin:0}img{width:100%;height:560px;object-fit:contain}
figcaption{text-align:center;font-size:14px;color:#706557}
nav{display:flex;flex-wrap:wrap;gap:8px 24px;margin-top:20px}
@media(max-width:700px){main{padding:20px 14px}h1{font-size:34px}.figures{gap:8px}img{height:300px}figcaption{font-size:11px}}
</style><main>
<p>Root GDR · studio 02</p><h1>Questa volta, i contorni li trova OpenCV.</h1>
<p class="intro">Rilevamento del foglio, correzione della prospettiva, isolamento del
disegno e separazione delle regioni tramite i bordi scuri. Tutti i vertici e i
colori vengono dai pixel. Gli stessi parametri sono usati per i tre personaggi.
Altus conserva il mantello. Le regioni non hanno ancora significato anatomico.</p>
<nav><a href="comparison.png" target="_blank">Confronto PNG completo</a>
<a href="../study.zip" download>Scarica SVG, PNG e codice Python</a>
<a href="../humanart/">Nuova prova di posa con HumanArt</a>
<a href="../index.html">Prima prova manuale</a></nav>
ROWS
<p class="intro">La soglia di semplificazione è espressa nei pixel della foto
raddrizzata. Una soglia bassa conserva curve e irregolarità; una più alta riduce
i vertici. Le zone chiare chiuse sono conservate: il programma non sa ancora
distinguere la carta visibile da una parte bianca del personaggio.</p>
POSE
</main></html>""".replace("ROWS", "".join(rows)).replace("POSE", pose)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--photos", type=Path, nargs=3, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "output" / "opencv")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    summaries = []
    for (slug, name), path in zip(NAMES, args.photos, strict=True):
        photo = cv2.cvtColor(
            np.array(ImageOps.exif_transpose(Image.open(path)).convert("RGB")),
            cv2.COLOR_RGB2BGR,
        )
        paper, corners, transform = rectify(photo)
        image, silhouette, ink, box = extract(paper)
        cv2.imwrite(str(args.output / f"{slug}-paper.png"), paper)
        x0, y0, x1, y1 = box
        cv2.imwrite(str(args.output / f"{slug}-rectified.png"), paper[y0:y1, x0:x1])
        isolated = image.copy()
        isolated[silhouette == 0] = (245, 245, 245)
        cv2.imwrite(str(args.output / f"{slug}-isolated.png"), isolated)
        cv2.imwrite(str(args.output / f"{slug}-ink.png"), ink)
        detection = photo.copy()
        cv2.polylines(detection, [np.int32(corners)], True, (40, 210, 40), 4)
        original_box = cv2.perspectiveTransform(
            np.float32([[[x0, y0], [x1, y0], [x1, y1], [x0, y1]]]),
            np.linalg.inv(transform),
        ).astype(np.int32)
        cv2.polylines(detection, original_box, True, (20, 30, 240), 3)
        cv2.imwrite(str(args.output / f"{slug}-detection.png"), detection)
        for suffix, epsilon in (("contours", 0.8), ("polygons", 3.0)):
            trace = Trace(
                name=name,
                width=image.shape[1],
                height=image.shape[0],
                paper_corners=corners.tolist(),
                crop_on_rectified_paper=box,
                epsilon_pixels=epsilon,
                regions=regions(image, silhouette, ink, epsilon),
            )
            render(trace, args.output, f"{slug}-{suffix}")
            vertices = sum(len(loop) for r in trace.regions for loop in r.loops)
            print(
                f"{slug} {suffix}: {len(trace.regions) - 1} fills, {vertices} vertices"
            )
        summaries.append(trace)
        diagnostic = image.copy()
        rng = np.random.default_rng(42)
        for region in trace.regions[1:]:
            color = tuple(int(v) for v in rng.integers(40, 230, size=3))
            loops = [np.array(loop, np.int32) for loop in region.loops]
            cv2.drawContours(diagnostic, loops, -1, color, cv2.FILLED)
            cv2.polylines(diagnostic, loops, True, (30, 30, 30), 1)
        cv2.imwrite(str(args.output / f"{slug}-regions.png"), diagnostic)
    comparison(args.output, summaries)
    gallery(args.output, summaries)


if __name__ == "__main__":
    main()
