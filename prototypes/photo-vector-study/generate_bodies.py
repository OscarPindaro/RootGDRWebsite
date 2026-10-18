# /// script
# requires-python = ">=3.12"
# dependencies = ["pydantic==2.12.5", "pillow==12.0.0", "cairosvg==2.8.2", "shapely==2.1.2"]
# ///
"""OpenPose-driven skin with pointed hands and a separately attached head."""

import argparse
from pathlib import Path
import xml.etree.ElementTree as ET

import cairosvg
from PIL import Image, ImageDraw, ImageFont, ImageOps
from pydantic import BaseModel, TypeAdapter

from body_skin import Pose, SkinTarget, TorsoProfile, build_skin
from body_surface import build_surface
from scene_svg import svg
from study_scene import Scene

ROOT = Path(__file__).resolve().parent
NS = "{http://www.w3.org/2000/svg}"


class TorsoVariant(BaseModel):
    id: str
    name: str
    torso: TorsoProfile


class TorsoStudy(BaseModel):
    base_pose: str
    profiles: list[TorsoVariant]


def asset_svg(scene: Scene, target: SkinTarget) -> bytes:
    root = ET.fromstring(svg(scene))
    head = ET.Element(
        NS + "g",
        {
            "id": target.head_attachment.svg_group,
            "data-anchor": "Neck",
            "data-aim": "Nose",
            "data-pivot": f"{target.head_attachment.pivot[0]} {target.head_attachment.pivot[1]}",
        },
    )
    for group in list(root):
        if group.attrib.get("data-part") == "head":
            root.remove(group)
            head.append(group)
    root.append(head)
    return ET.tostring(root) + b"\n"


def construction_svg(data: bytes, target: SkinTarget) -> bytes:
    root = ET.fromstring(data)
    guides = ET.SubElement(
        root, NS + "g", {"id": "construction", "fill": "none", "stroke-width": "2"}
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
                "stroke": "#285d86",
                "stroke-dasharray": "5 4",
            },
        )
    for section in target.sections:
        ET.SubElement(
            guides,
            NS + "line",
            {
                "x1": str(section.left[0]),
                "y1": str(section.left[1]),
                "x2": str(section.right[0]),
                "y2": str(section.right[1]),
                "stroke": "#d26936",
            },
        )
        for x, y in (section.left, section.right):
            dot = ET.SubElement(
                guides,
                NS + "circle",
                {
                    "cx": str(x),
                    "cy": str(y),
                    "r": "3",
                    "fill": "#fff7db",
                    "stroke": "#d26936",
                },
            )
            ET.SubElement(
                dot, NS + "title"
            ).text = f"{section.joint}: offset {section.offset:g}"
    for name, (x, y) in target.joints.items():
        dot = ET.SubElement(
            guides,
            NS + "circle",
            {
                "cx": str(x),
                "cy": str(y),
                "r": "3",
                "fill": "#285d86",
                "stroke": "#fff7db",
                "stroke-width": "1",
            },
        )
        ET.SubElement(dot, NS + "title").text = name
    for name, (x, y) in target.hand_tips.items():
        dot = ET.SubElement(
            guides,
            NS + "circle",
            {
                "cx": str(x),
                "cy": str(y),
                "r": "3",
                "fill": "#d26936",
            },
        )
        ET.SubElement(
            dot, NS + "title"
        ).text = f"Hand tip from {name}; not an extra pose keypoint"
    for station in target.torso_sections:
        group = ET.SubElement(
            guides, NS + "g", {"stroke": "#3d7850", "stroke-width": "3"}
        )
        ET.SubElement(
            group,
            NS + "line",
            {
                "x1": str(station.left[0]),
                "y1": str(station.left[1]),
                "x2": str(station.right[0]),
                "y2": str(station.right[1]),
            },
        )
        for x, y in (station.left, station.center, station.right):
            dot = ET.SubElement(
                group,
                NS + "circle",
                {
                    "cx": str(x),
                    "cy": str(y),
                    "r": "4",
                    "fill": "#f4f0e5",
                },
            )
            ET.SubElement(
                dot, NS + "title"
            ).text = f"{station.control}: {station.half_width * 2:g}px"
    return ET.tostring(root) + b"\n"


def gallery(
    poses: list[Pose], targets: list[SkinTarget], output: Path, *, torso_study=False
) -> None:
    cards = []
    board = Image.new("RGB", (len(poses) * 375 + 25, 990), "#f4f0e5")
    ink = ImageDraw.Draw(board)
    font = "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf"
    title, small = ImageFont.truetype(font, 32), ImageFont.truetype(font, 17)
    ink.text(
        (30, 25),
        "Petto e addome · stesso scheletro"
        if torso_study
        else "OpenPose · corpo continuo e testa separata",
        font=title,
        fill="#302d2b",
    )
    ink.text(
        (30, 82),
        "Cambiano solo altezza e larghezza dei controlli del busto"
        if torso_study
        else "COCO_18 · nessun collo aggiunto · mani a punta · nessuna sporgenza centrale",
        font=small,
        fill="#786e61",
    )
    bounds = [Image.open(output / f"{pose.id}.png").getbbox() for pose in poses]
    common = (
        min(b[0] for b in bounds),
        min(b[1] for b in bounds),
        max(b[2] for b in bounds),
        max(b[3] for b in bounds),
    )
    for index, (pose, target) in enumerate(zip(poses, targets, strict=True)):
        original = Image.open(output / f"{pose.id}.png")
        image = ImageOps.contain(original.crop(common), (345, 725))
        board.paste(
            image,
            (
                25 + index * 375 + (345 - image.width) // 2,
                135 + (725 - image.height) // 2,
            ),
            image,
        )
        ink.text((25 + index * 375, 900), pose.name, font=small, fill="#302d2b")
        ink.text(
            (25 + index * 375, 934),
            f"Corpo: {len(target.body_vertices)} vertici · testa indipendente",
            font=small,
            fill="#786e61",
        )
        controls = " · ".join(
            f"{'Petto' if station.control == 'chest' else 'Addome'}: {station.half_width * 2:g}px"
            for station in target.torso_sections
        )
        cards.append(f"""
        <article><h2>{pose.name}</h2><p>Corpo continuo e testa indipendente, agganciata alla posa.</p>
        <p>{controls}</p>
        <figure><img data-id="{pose.id}" src="{pose.id}.svg" alt="{pose.name}"></figure>
        <nav><a href="{pose.id}.svg" download>SVG</a><a href="{pose.id}.json" download>Scena</a>
        <a href="{pose.id}-target.json" download>Giunti e offset</a>
        <a href="{pose.id}-openpose.json" download>OpenPose JSON</a>
        <a href="{pose.id}-construction.svg" target="_blank">Costruzione</a></nav></article>""")
    board.save(output / "preview.png")
    references = (
        """
    <section class="references"><figure><a href="../references/j-como.jpg" target="_blank">
    <img src="../references/j-como.jpg" alt="J. Como Salvasterzi, disegno originale"></a>
    <figcaption>J. Como · fianchi del torace più verticali</figcaption></figure>
    <figure><a href="../references/lizaard.jpg" target="_blank">
    <img src="../references/lizaard.jpg" alt="Lizaárd al Gaib, disegno originale"></a>
    <figcaption>Lizaárd · petto largo e addome stretto</figcaption></figure></section>
    """
        if torso_study
        else ""
    )
    heading = (
        "Tre profili del busto, una sola posa."
        if torso_study
        else "Corpo continuo, testa indipendente."
    )
    introduction = (
        """
    <p>Stesso OpenPose, stessi arti, stessi offset e stessa testa.
    Cambiano soltanto i controlli della sagoma: altezza e larghezza del petto,
    più un controllo opzionale per l’addome. Non sono nuove ossa.
    Il petto largo richiama Tacito e Lizaárd; il profilo rettilineo richiama J. Como.</p>
    """
        if torso_study
        else ""
    )
    (output / "index.html").write_text(
        """<!doctype html><html lang="it"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Corpo continuo dalle bisettrici</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f4f0e5;color:#302d2b;font:16px/1.5 Georgia,serif}
main{max-width:1600px;margin:auto;padding:34px}h1{font-size:44px;font-weight:normal;margin:18px 0}
p{max-width:940px;color:#706453}.controls{display:flex;flex-wrap:wrap;gap:28px;margin:24px 0}
label,nav,.legend{font:14px/1.5 system-ui,sans-serif}
label{display:flex;gap:10px;align-items:center;min-height:44px;cursor:pointer}input{width:20px;height:20px}
.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:22px}
article{background:#faf7ef;border:1px solid #cfc4b1;padding:22px}h2{font-weight:normal;font-size:28px}
figure{margin:0}img{width:100%;height:620px;object-fit:contain}nav{display:flex;flex-wrap:wrap;gap:20px}
a{display:inline-flex;align-items:center;min-height:44px;color:#365b70}
a:focus-visible,input:focus-visible{outline:3px solid #d26936;outline-offset:4px}
.bone{color:#285d86}.flesh{color:#bb572a}
.torso{color:#3d7850}.references{display:flex;gap:28px;flex-wrap:wrap;margin-top:30px}
.references img{width:250px;height:300px;object-fit:contain}.references figcaption{font-size:14px}
@media(max-width:1100px){.grid{grid-template-columns:1fr 1fr}}
@media(max-width:650px){main{padding:20px 14px}.grid{grid-template-columns:1fr}}
</style><main><p>Root GDR · studio della pelle continua</p>
<h1>HEADING</h1>
INTRODUCTION
<p>Lo scheletro usa il formato OpenPose COCO_18. Il corpo resta un’unica sagoma,
senza colonna del collo né punto pubico aggiunto. Le mani terminano a punta.
La testa è una forma separata: il suo pivot segue Neck e l’orientamento segue Nose.
Può muoversi senza riscrivere il corpo.</p>
<div class="controls"><label><input id="guides" type="checkbox">Mostra scheletro, bisettrici e punti della pelle</label>
<a href="preview.png" target="_blank">Tavola PNG</a><a href="../shapes/">Studio dalle fotografie</a>
<a href="../torso/">Confronto dei profili del busto</a><a href="../generated/">Cinque pose di base</a>
<a href="../intersections/">Raccordo con intersezioni e bordi davanti</a>
<a href="../study.zip" download>Scarica lo studio</a></div>
<p class="legend"><span class="bone">Blu: ossa e centri dei giunti.</span>
<span class="flesh">Arancio: bisettrici e due estremi dell’offset.</span>
<span class="torso">Verde: controlli della sagoma del busto, separati dallo scheletro.</span>
Le guide non sono bordi del corpo e non compaiono nell’SVG pulito.
Tutti gli esempi usano la stessa scala.</p>
<section class="grid">CARDS</section>
REFERENCES
<p>Neck è un riferimento OpenPose al centro delle spalle, non un collo da disegnare.
Nose posiziona e orienta la forma della testa; non esistono ossa personalizzate
“head”, “jaw” o “crotch”. Le pose, i profili delle teste e gli spessori sono dichiarati. Il contorno è
calcolato da quelle informazioni. Gli offset sono misurati lungo la bisettrice;
non viene applicata una correzione miter che allunghi gli angoli.
Per i profili del busto, le intersezioni tra superfici determinano il contorno
e gli arti davanti conservano i bordi visibili, senza chiusure artificiali sui giunti.
Gli arti completamente ripiegati sono ancora rifiutati.</p>
</main><script>
document.querySelector('#guides').addEventListener('change', event => {
  for (const image of document.querySelectorAll('img[data-id]')) {
    image.src = image.dataset.id + (event.target.checked ? '-construction.svg' : '.svg');
  }
});
</script></html>""".replace("CARDS", "".join(cards))
        .replace("HEADING", heading)
        .replace("INTRODUCTION", introduction)
        .replace("REFERENCES", references)
        + "\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--torso-study", action="store_true")
    args = parser.parse_args()
    poses = TypeAdapter(list[Pose]).validate_json(
        (ROOT / "edits/naked-poses.json").read_text()
    )
    if args.torso_study:
        study = TorsoStudy.model_validate_json(
            (ROOT / "edits/torso-profiles.json").read_text()
        )
        base = next((p for p in poses if p.id == study.base_pose), None)
        if base is None:
            parser.error(f"Unknown base pose: {study.base_pose}")
        poses = [
            base.model_copy(
                deep=True, update={"id": v.id, "name": v.name, "torso": v.torso}
            )
            for v in study.profiles
        ]
    output = ROOT / ("output/torso" if args.torso_study else "output/generated")
    output.mkdir(parents=True, exist_ok=True)
    targets = []
    for pose in poses:
        scene, target = build_surface(pose) if pose.torso else build_skin(pose)
        targets.append(target)
        data = asset_svg(scene, target)
        (output / f"{pose.id}.svg").write_bytes(data)
        (output / f"{pose.id}-construction.svg").write_bytes(
            construction_svg(data, target)
        )
        (output / f"{pose.id}.json").write_text(scene.model_dump_json(indent=2) + "\n")
        (output / f"{pose.id}-target.json").write_text(
            target.model_dump_json(indent=2) + "\n"
        )
        (output / f"{pose.id}-openpose.json").write_text(
            pose.openpose.model_dump_json(indent=2) + "\n"
        )
        cairosvg.svg2png(
            bytestring=data,
            write_to=str(output / f"{pose.id}.png"),
            output_width=scene.width,
            output_height=scene.height,
        )
        print(
            f"{pose.id}: one skin contour, {len(target.sections)} cross-sections",
            flush=True,
        )
    gallery(poses, targets, output, torso_study=args.torso_study)


if __name__ == "__main__":
    main()
