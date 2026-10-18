# /// script
# requires-python = ">=3.12"
# dependencies = ["pydantic==2.12.5", "pillow==12.0.0", "cairosvg==2.8.2", "shapely==2.1.2"]
# ///
"""One asymmetric, shoulder-based intersection study matching Oscar's sketch."""

from pathlib import Path
import xml.etree.ElementTree as ET

import cairosvg
from PIL import Image, ImageDraw, ImageFont, ImageOps
from shapely.geometry import LineString, Point as GPoint, Polygon as GPolygon
from shapely.ops import unary_union

from body_skin import Pose
from body_surface import SurfaceTarget, build_surface
from generate_bodies import asset_svg

ROOT = Path(__file__).resolve().parent
NS = "{http://www.w3.org/2000/svg}"


def diagnostic_svg(data: bytes, target: SurfaceTarget) -> bytes:
    root = ET.fromstring(data)
    guides = ET.SubElement(root, NS + "g", {"id": "surface-guides", "fill": "none"})
    for component in target.components:
        ET.SubElement(
            guides,
            NS + "polygon",
            {
                "points": " ".join(f"{x:g},{y:g}" for x, y in component.outline),
                "stroke": "#a268b4" if component.id == "torso" else "#d28b40",
                "stroke-width": "1.5",
                "stroke-dasharray": "5 4",
            },
        )
    for bone in target.bones:
        a, b = target.joints[bone.start], target.joints[bone.end]
        ET.SubElement(
            guides,
            NS + "line",
            {
                "x1": str(a[0]),
                "y1": str(a[1]),
                "x2": str(b[0]),
                "y2": str(b[1]),
                "stroke": "#278357",
                "stroke-width": "2",
            },
        )
    for crossing in target.crossings:
        ET.SubElement(
            guides,
            NS + "circle",
            {
                "cx": str(crossing.point[0]),
                "cy": str(crossing.point[1]),
                "r": "3",
                "fill": "#d34f3f",
            },
        )
    for label, (x, y) in target.reference_markers.items():
        color = "#d34f3f" if label == "6" else "#216e9f"
        ET.SubElement(
            guides,
            NS + "circle",
            {
                "cx": str(x),
                "cy": str(y),
                "r": "6",
                "fill": "#fff4dc",
                "stroke": color,
                "stroke-width": "2",
            },
        )
        text = ET.SubElement(
            guides,
            NS + "text",
            {
                "x": str(x - 24 if label == "6" else x + 10),
                "y": str(y + 5),
                "fill": color,
                "font-family": "serif",
                "font-size": "20",
                "font-weight": "bold",
            },
        )
        text.text = label
    return ET.tostring(root) + b"\n"


def verify(target: SurfaceTarget) -> None:
    surfaces = {c.id: GPolygon(c.outline) for c in target.components}
    body = GPolygon(target.body_vertices, target.body_holes)
    expected = unary_union(list(surfaces.values()))
    if body.symmetric_difference(expected).area > 1e-6:
        raise ValueError("The exported contour does not match the construction union.")
    six, twelve = target.reference_markers["6"], target.reference_markers["12"]
    for name in ("torso", "arm-R"):
        if surfaces[name].boundary.distance(GPoint(six)) > 1e-6:
            raise ValueError("Reference 6 is not a calculated torso/arm intersection.")
    if body.exterior.distance(GPoint(twelve)) > 1e-6:
        raise ValueError("Reference 12 was lost from the outer contour.")
    if not target.occlusion_edges:
        raise ValueError("The overlapping foreground arm lost its visible border.")
    shown = unary_union(
        [LineString(edge.points) for edge in target.occlusion_edges if edge.arm == "R"]
    )
    sections = {section.joint: section for section in target.sections}
    upper = LineString([sections["RShoulder"].right, sections["RElbow"].right])
    if upper.difference(shown).length > 1e-6:
        raise ValueError("The internal upper-arm edge highlighted by Oscar is missing.")
    for joint in ("RShoulder", "RElbow"):
        cap = LineString([sections[joint].left, sections[joint].right])
        if cap.intersection(shown).length > 1e-6:
            raise ValueError(f"An artificial joint cap was rendered at {joint}.")
    for edge in target.occlusion_edges:
        line = LineString(edge.points)
        if line.difference(surfaces["torso"]).length > 1e-6:
            raise ValueError("An occlusion edge escaped the torso.")
    print(
        f"Verified: 6 is a boundary intersection; 12 survives; "
        f"{len(target.occlusion_edges)} foreground edge(s); {len(target.body_holes)} hole(s)."
    )


def main() -> None:
    output = ROOT / "output/intersections"
    output.mkdir(parents=True, exist_ok=True)
    pose = Pose.model_validate_json((ROOT / "edits/intersection-pose.json").read_text())
    # The image-left arm is in front; the raised arm joins the silhouette
    # without an extra internal shoulder edge. Depth is not given by OpenPose.
    scene, target = build_surface(pose, foreground_arms=("R",))
    verify(target)
    data = asset_svg(scene, target)
    guides = diagnostic_svg(data, target)
    (output / "body.svg").write_bytes(data)
    (output / "construction.svg").write_bytes(guides)
    (output / "scene.json").write_text(scene.model_dump_json(indent=2) + "\n")
    (output / "target.json").write_text(target.model_dump_json(indent=2) + "\n")
    (output / "openpose.json").write_text(
        pose.openpose.model_dump_json(indent=2) + "\n"
    )
    for name, content in (("body", data), ("construction", guides)):
        cairosvg.svg2png(
            bytestring=content, write_to=str(output / f"{name}.png"), output_height=820
        )
    board = Image.new("RGB", (1500, 1000), "#f4f0e5")
    ink = ImageDraw.Draw(board)
    font = "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf"
    title, small = ImageFont.truetype(font, 30), ImageFont.truetype(font, 19)
    ink.text(
        (30, 25),
        "Un solo caso · intersezioni tra busto e arti",
        font=title,
        fill="#302d2b",
    )
    inputs = [
        Image.open(ROOT / "output/references/numbered-body.png").crop(
            (140, 280, 620, 880)
        ),
        Image.open(output / "body.png"),
        Image.open(output / "construction.png"),
    ]
    for index, (image, label) in enumerate(
        zip(
            inputs,
            [
                "Il tuo schema",
                "Bordo interno del braccio completo",
                "6: intersezione · 12: vertice del busto",
            ],
        )
    ):
        image = ImageOps.contain(image.convert("RGBA"), (450, 800))
        board.paste(
            image,
            (
                30 + index * 490 + (450 - image.width) // 2,
                100 + (800 - image.height) // 2,
            ),
            image,
        )
        ink.text((30 + index * 490, 930), label, font=small, fill="#302d2b")
    board.save(output / "preview.png")
    (
        output / "index.html"
    ).write_text("""<!doctype html><html lang="it"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Busto e arti: intersezioni</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f4f0e5;color:#302d2b;font:17px/1.5 Georgia,serif}
main{max-width:1500px;margin:auto;padding:30px}h1{font-size:42px;font-weight:normal}
p{max-width:1000px}.figures{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:24px}
figure{margin:0}img{width:100%;height:700px;object-fit:contain}figcaption{font-size:15px}
a{color:#365b70;display:inline-flex;align-items:center;min-height:44px;margin-right:20px}
@media(max-width:800px){.figures{grid-template-columns:1fr}main{padding:20px 14px}}
</style><main><h1>L’ascella viene dall’intersezione.</h1>
<p>Il busto parte dalle spalle, con la propria sagoma. Le superfici degli arti
sono costruite dalle bisettrici. L’unione geometrica determina il contorno finale:
il punto 6 è calcolato dove si incontrano arto e busto; il 12 rimane perché
il braccio alzato non lo copre. Il braccio davanti conserva il bordo interno
sia sopra sia sotto il gomito, incluso il tratto indicato in rosso.
Non vengono disegnate le chiusure di costruzione alla spalla o al gomito.</p>
<p>6 e 12 richiamano il tuo schema: non sono indici imposti all’array dei vertici.
La posa è ricostruita a mano per la prova; intersezioni e bordi visibili sono calcolati.</p>
<section class="figures">
<figure><a href="../references/numbered-body.png" target="_blank"><img src="../references/numbered-body.png" alt="Schema numerato originale"></a><figcaption>Schema di riferimento</figcaption></figure>
<figure><img src="body.svg" alt="Unico contorno e bordo dell’avambraccio davanti"><figcaption>Risultato senza guide</figcaption></figure>
<figure><img src="construction.svg" alt="Superfici, scheletro e intersezioni 6 e 12"><figcaption>Viola: busto · arancio: arti · verde: scheletro</figcaption></figure>
</section><p><a href="body.svg" download>SVG</a><a href="scene.json" download>Scena</a>
<a href="target.json" download>Geometria e intersezioni</a><a href="openpose.json" download>OpenPose</a>
<a href="preview.png">Tavola PNG</a><a href="../torso/">Profili del busto</a></p>
<p>Le superfici di costruzione non sono parti disegnate separatamente: l’immagine
ha un unico elemento di pelle, con eventuali fori, più le sole linee di occlusione
necessarie e la testa indipendente. I fori non vengono riempiti automaticamente.</p>
</main></html>\n""")


if __name__ == "__main__":
    main()
