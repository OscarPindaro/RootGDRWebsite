"""SVG serialization shared by extracted and procedurally authored scenes."""

import xml.etree.ElementTree as ET

from study_scene import Bezier, Ellipse, Polygon, Scene


def svg(scene: Scene, parts: bool = False) -> bytes:
    root = ET.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "viewBox": f"0 0 {scene.width} {scene.height}",
            "width": str(scene.width),
            "height": str(scene.height),
            "stroke-linejoin": "round",
            "stroke-linecap": "round",
            "role": "img",
            "aria-label": scene.name,
        },
    )
    colors = ["#d48672", "#61a2b8", "#b7ad59", "#9985b9", "#7ba17a", "#cb89a5"]
    for index, shape in enumerate(scene.shapes):
        group = ET.SubElement(
            root,
            "g",
            {
                "id": shape.id,
                "data-kind": shape.kind,
                "data-label": shape.label or shape.id,
                "data-part": shape.part or shape.id,
                "data-source": shape.source_region,
                "tabindex": "0",
            },
        )
        ET.SubElement(group, "title").text = f"{shape.label or shape.id} · {shape.kind}"
        style = {
            "fill": colors[index % len(colors)]
            if parts and shape.fill != "none"
            else shape.fill,
            "stroke": shape.stroke,
            "stroke-width": str(shape.stroke_width),
        }
        if isinstance(shape, Polygon):
            ET.SubElement(
                group,
                shape.kind,
                {
                    **style,
                    "points": " ".join(f"{x:g},{y:g}" for x, y in shape.points),
                },
            )
        elif isinstance(shape, Ellipse):
            x, y = shape.center
            ET.SubElement(
                group,
                "ellipse",
                {
                    **style,
                    "cx": str(x),
                    "cy": str(y),
                    "rx": str(shape.radii[0]),
                    "ry": str(shape.radii[1]),
                    "transform": f"rotate({shape.rotation} {x} {y})",
                },
            )
        elif isinstance(shape, Bezier):
            d = f"M {shape.start[0]:g},{shape.start[1]:g} "
            for segment in shape.segments:
                d += (
                    "C "
                    + " ".join(
                        f"{x:g},{y:g}"
                        for x, y in (segment.control1, segment.control2, segment.end)
                    )
                    + " "
                )
            ET.SubElement(group, "path", {**style, "d": d})
        else:
            d = " ".join(
                "M " + " L ".join(f"{x:g},{y:g}" for x, y in loop) + " Z"
                for loop in shape.loops
            )
            ET.SubElement(group, "path", {**style, "d": d, "fill-rule": "evenodd"})
    ET.indent(root)
    return ET.tostring(root, encoding="utf-8") + b"\n"
