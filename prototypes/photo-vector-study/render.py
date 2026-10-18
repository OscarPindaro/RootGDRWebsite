# /// script
# requires-python = ">=3.12"
# dependencies = ["cairosvg==2.8.2", "pillow==12.0.0", "pydantic==2.12.5"]
# ///
"""Render the annotated polygon studies. Run with `uv run render.py --help`."""

import argparse
from html import escape
from pathlib import Path
import xml.etree.ElementTree as ET

import cairosvg
from PIL import Image, ImageDraw, ImageFont, ImageOps

from drawings import DRAWINGS, Drawing

ROOT = Path(__file__).resolve().parent
PAPER = "#f4f0e5"
PART_COLORS = [
    "#e66b52",
    "#43a6b5",
    "#b1a34d",
    "#9682bd",
    "#d79852",
    "#629475",
    "#cd6c9a",
    "#718fc9",
    "#98aa58",
    "#a37d64",
    "#6db9b1",
    "#c8a6b9",
    "#dcab48",
    "#79949b",
    "#bf8871",
]


def svg(drawing: Drawing, parts: bool = False) -> bytes:
    x0, y0, x1, y1 = drawing.crop
    root = ET.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "viewBox": f"{x0} {y0} {x1 - x0} {y1 - y0}",
            "width": str(x1 - x0),
            "height": str(y1 - y0),
            "stroke-linejoin": "round",
            "stroke-linecap": "round",
            "role": "img",
            "aria-labelledby": "title description",
        },
    )
    ET.SubElement(root, "title", id="title").text = drawing.title
    ET.SubElement(root, "desc", id="description").text = (
        "Polygon reconstruction manually interpreted from the supplied photo. "
        "Named groups describe visible parts; they are not an inferred skeleton."
    )
    for index, part in enumerate(drawing.parts):
        group = ET.SubElement(root, "g", id=part.name, attrib={"data-part": part.name})
        ET.SubElement(group, "title").text = part.name
        for shape in part.shapes:
            fill = PART_COLORS[index % len(PART_COLORS)] if parts else shape.fill
            ET.SubElement(
                group,
                shape.kind,
                {
                    "id": f"{part.name}--{shape.name}",
                    "points": " ".join(f"{x:g},{y:g}" for x, y in shape.points),
                    "fill": fill if shape.kind == "polygon" else "none",
                    "stroke": "#302d2b" if parts else shape.stroke,
                    "stroke-width": "1.4" if parts else str(shape.width),
                },
            )
            if parts:
                for x, y in shape.points:
                    ET.SubElement(
                        group,
                        "circle",
                        {
                            "cx": str(x),
                            "cy": str(y),
                            "r": "1.7",
                            "fill": "#302d2b",
                            "stroke": "none",
                        },
                    )
    ET.indent(root)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def sheet(output: Path, comparison: bool) -> None:
    """Create a readable preview without changing the transparent exports."""
    cell_width, image_height = (620, 600) if comparison else (440, 650)
    board = Image.new("RGB", (cell_width * 3 + 80, image_height + 260), PAPER)
    ink = ImageDraw.Draw(board)
    font_path = "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf"
    title_font = ImageFont.truetype(font_path, 32)
    name_font = ImageFont.truetype(font_path, 22)
    small_font = ImageFont.truetype(font_path, 15)
    ink.text((40, 30), "Dalla carta ai poligoni", fill="#302d2b", font=title_font)
    ink.text(
        (40, 80),
        "Studio 01 · ricostruzione guidata dalle fotografie · SVG a gruppi separati",
        fill="#766b61",
        font=small_font,
    )
    for index, drawing in enumerate(DRAWINGS):
        left = 40 + index * cell_width
        figure = Image.open(output / f"{drawing.slug}.png").convert("RGBA")
        if comparison:
            reference = Image.open(output / f"{drawing.slug}-reference.png")
            for offset, image in [(0, reference), (cell_width // 2, figure)]:
                image = ImageOps.contain(image, (cell_width // 2 - 24, image_height))
                position = (
                    left + offset + (cell_width // 2 - 24 - image.width) // 2,
                    132 + (image_height - image.height) // 2,
                )
                board.paste(image, position, image if image.mode == "RGBA" else None)
            ink.text((left, 110), "FOTOGRAFIA", fill="#766b61", font=small_font)
            ink.text(
                (left + cell_width // 2, 110), "SVG", fill="#766b61", font=small_font
            )
        else:
            figure = ImageOps.contain(figure, (cell_width - 50, image_height))
            board.paste(
                figure,
                (
                    left + (cell_width - 50 - figure.width) // 2,
                    130 + (image_height - figure.height) // 2,
                ),
                figure,
            )
        ink.text(
            (left, image_height + 158), drawing.title, fill="#302d2b", font=name_font
        )
        polygons = sum(s.kind == "polygon" for p in drawing.parts for s in p.shapes)
        ink.text(
            (left, image_height + 193),
            f"{len(drawing.parts)} gruppi · {polygons} poligoni",
            fill="#766b61",
            font=small_font,
        )
        if index == 0:
            ink.text(
                (left, image_height + 218),
                "Mantello omesso",
                fill="#766b61",
                font=small_font,
            )
    board.save(output / ("comparison.png" if comparison else "preview.png"))


def gallery(output: Path) -> None:
    cards = []
    for drawing in DRAWINGS:
        polygons = sum(s.kind == "polygon" for p in drawing.parts for s in p.shapes)
        reference = output / f"{drawing.slug}-reference.png"
        photo = (
            (
                f'<figure><img src="{reference.name}" alt="Foto di {escape(drawing.title)}">'
                "<figcaption>Fotografia</figcaption></figure>"
            )
            if reference.exists()
            else ""
        )
        cards.append(f"""
        <article>
          <header><h2>{escape(drawing.title)}</h2>
          <span>{len(drawing.parts)} gruppi · {polygons} poligoni</span></header>
          <p>{escape(drawing.note)}</p>
          <div class="pair">{photo}<figure>
          <img class="vector" data-slug="{drawing.slug}" src="{drawing.slug}.svg"
               alt="Ricostruzione di {escape(drawing.title)}">
          <figcaption>Ricostruzione SVG</figcaption></figure></div>
          <nav aria-label="File di {escape(drawing.title)}">
          <a href="{drawing.slug}.svg" download>Scarica SVG</a>
          <a href="{drawing.slug}.png" download>PNG trasparente</a>
          <a href="{drawing.slug}-parts.svg" target="_blank">Mappa dei gruppi</a>
          <a href="{drawing.slug}.json" download>Poligoni JSON</a></nav>
        </article>""")
    html = """<!doctype html>
<html lang="it"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dalla carta ai poligoni · Studio 01</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#f4f0e5;color:#302d2b;font:16px/1.5 system-ui,sans-serif}
main{max-width:1540px;margin:auto;padding:36px 28px}
.eyebrow{letter-spacing:.13em;text-transform:uppercase;font-size:12px;color:#776d61}
h1{font:clamp(32px,5vw,56px)/1.1 Georgia,serif;margin:14px 0}
.intro{max-width:780px;color:#665d53}
.controls{display:flex;align-items:center;gap:18px;flex-wrap:wrap;margin:26px 0}
label{display:flex;align-items:center;gap:10px;min-height:44px;cursor:pointer}
input{width:20px;height:20px;accent-color:#302d2b}
.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}
article{border:1px solid #cfc7b8;background:#faf7f0;padding:22px}
h2{font:26px/1.2 Georgia,serif;margin:0 0 8px}
article header span,article p,figcaption{font-size:13px;color:#746a5f}
article p{min-height:40px}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:12px}
figure{margin:0;min-width:0}
figure img{display:block;width:100%;height:390px;object-fit:contain}
figcaption{margin:12px 0;text-align:center}
nav{display:flex;gap:0 16px;flex-wrap:wrap;border-top:1px solid #ddd4c6;padding-top:12px}
a{color:#365b70;text-underline-offset:4px;display:inline-flex;align-items:center;min-height:44px}
a:focus-visible,input:focus-visible{outline:3px solid #008ed0;outline-offset:4px}
footer{margin:24px 0;color:#746a5f;font-size:14px;max-width:850px}
@media(max-width:1100px){.grid{grid-template-columns:1fr}figure img{height:520px}}
@media(max-width:540px){main{padding:24px 14px}article{padding:16px}figure img{height:300px}.pair{gap:8px}}
</style>
<main>
<div class="eyebrow">Root GDR · laboratorio di disegno · studio 01</div>
<h1>Dalla carta ai poligoni.</h1>
<p class="intro">Tre personaggi ricostruiti osservando le tue fotografie.
Contorni puliti, colori piatti e parti separate. Altus è senza mantello;
le parti nascoste nel disegno restano da definire.</p>
<div class="controls">
<label><input id="parts" type="checkbox">Mostra gruppi e vertici</label>
<a href="preview.png" target="_blank">Apri la tavola PNG</a>
<a href="comparison.png" target="_blank">Confronto completo</a>
<a href="opencv/index.html">Nuova prova automatica con OpenCV</a>
<a href="humanart/index.html">Pose con modelli HumanArt</a>
<a href="shapes/index.html">Bordi puliti e oggetti separati</a>
<a href="pose-comparison/index.html">Confronto dei tre modelli di posa</a>
</div>
<section class="grid">CARDS</section>
<footer>Questa prima prova è una ricostruzione guidata, con punti scelti osservando
le immagini. I gruppi descrivono le parti visibili: non sono ancora uno scheletro
né un’importazione nel canvas. Gli SVG e i PNG dei singoli personaggi hanno
sfondo trasparente.</footer>
POSE
</main>
<script>
document.querySelector('#parts').addEventListener('change', event => {
  for (const image of document.querySelectorAll('.vector')) {
    image.src = image.dataset.slug + (event.target.checked ? '-parts.svg' : '.svg');
  }
});
</script></html>
""".replace("CARDS", "".join(cards))
    pose = ""
    if (output / "luciano-pose-crop-0.25.png").exists():
        pose = """
        <details><summary>La prova di stima della posa</summary>
        <p>MediaPipe non rileva pose con le soglie standard. Abbassandole a 0,25
        compare questo tentativo su Luciano: i punti non seguono ali e zampe.</p>
        <a href="luciano-pose-crop-0.25.png" target="_blank">
        Apri il tentativo di MediaPipe</a> ·
        <a href="pose-results.json" download>Risultati delle 12 prove</a>
        </details>"""
    html = html.replace("POSE", pose)
    (output / "index.html").write_text(html)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--photos", type=Path, nargs=3, metavar=("ALTUS", "LUCIANO", "WOLF")
    )
    parser.add_argument("--output", type=Path, default=ROOT / "output")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for index, drawing in enumerate(DRAWINGS):
        image_svg = svg(drawing)
        (args.output / f"{drawing.slug}.svg").write_bytes(image_svg)
        (args.output / f"{drawing.slug}-parts.svg").write_bytes(
            svg(drawing, parts=True)
        )
        (args.output / f"{drawing.slug}.json").write_text(
            drawing.model_dump_json(indent=2)
        )
        cairosvg.svg2png(
            bytestring=image_svg,
            write_to=str(args.output / f"{drawing.slug}.png"),
            output_height=1400,
        )
        if args.photos:
            ImageOps.exif_transpose(Image.open(args.photos[index])).convert("RGB").crop(
                drawing.crop
            ).save(args.output / f"{drawing.slug}-reference.png")
        polygons = sum(s.kind == "polygon" for p in drawing.parts for s in p.shapes)
        print(f"{drawing.slug}: {len(drawing.parts)} groups, {polygons} polygons")
    sheet(args.output, comparison=False)
    if all((args.output / f"{d.slug}-reference.png").exists() for d in DRAWINGS):
        sheet(args.output, comparison=True)
    gallery(args.output)
    print(f"Preview: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
