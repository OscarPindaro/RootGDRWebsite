"""Guided layered variant: retain the first contours and author one complete sword.

The sword vertices and region classification are explicit author interpretations,
not an automatic amodal reconstruction. No raster is embedded in the result.
"""

import cv2
import numpy as np

from opencv_trace import Trace
from study_scene import Compound, INK, Polygon, Scene


def build_scene(trace: Trace) -> Scene:
    sword_regions = {
        "region-005",
        "region-045",
        "region-075",
        "region-190",
        "region-312",
    }
    head_regions = {
        "region-052",
        "region-094",
        "region-111",
        "region-117",
        "region-132",
        "region-136",
        "region-137",
        "region-138",
        "region-145",
    }
    scene = Scene(
        name=trace.name,
        width=trace.width,
        height=trace.height,
        shapes=[],
        method="Retained first-extraction contours with an authored complete background sword",
        interpretation="The first extraction remains the preferred reference; this is a guided layering alternative.",
    )
    blade = [(157, 78), (76, 157), (365, 458), (446, 475), (441, 390)]
    for id, points, fill, width in (
        ("sword-blade", blade, "#e1ddcd", 7),
        ("sword-bevel", [(157, 78), (116, 117), (446, 475), (441, 390)], "#b5b7b4", 1),
        ("sword-grip", [(24, 30), (34, 20), (109, 81), (75, 110)], "#c52d30", 7),
        (
            "sword-guard",
            [(55, 132), (129, 66), (159, 66), (166, 73), (67, 163), (57, 161)],
            "#c52d30",
            7,
        ),
    ):
        scene.shapes.append(
            Polygon(
                id=id,
                part="sword",
                label="Spada completa · dietro il personaggio",
                source_region="authored-from-sword-fragments",
                kind="polygon",
                points=points,
                fill=fill,
                stroke_width=width,
                stroke="none" if id == "sword-bevel" else INK,
            )
        )
    scene.shapes.insert(
        2,
        Polygon(
            id="sword-ridge",
            part="sword",
            label="Linea continua della lama",
            source_region="authored-from-sword-fragments",
            kind="polyline",
            points=[(116, 117), (446, 475)],
            fill="none",
            stroke_width=3.5,
        ),
    )
    # Recover the character's ink silhouette from its colour components, omitting
    # sword fragments. Original contour holes retain facial marks and stitches.
    body = np.zeros((trace.height, trace.width), np.uint8)
    original = np.zeros_like(body)
    cv2.drawContours(
        original,
        [np.int32(loop) for loop in trace.regions[0].loops],
        -1,
        255,
        cv2.FILLED,
    )
    fills = [r for r in trace.regions[1:] if r.id not in sword_regions]
    for region in fills:
        mask = np.zeros_like(body)
        cv2.drawContours(
            mask, [np.int32(loop) for loop in region.loops], -1, 255, cv2.FILLED
        )
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(body, contours, -1, 255, cv2.FILLED)
    body = cv2.dilate(body, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)))
    outside, _ = cv2.findContours(body, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(body, outside, -1, 255, cv2.FILLED)
    body &= original
    contours, _ = cv2.findContours(body, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    loops = [
        cv2.approxPolyDP(c, 0.6, True)[:, 0].tolist()
        for c in contours
        if cv2.contourArea(c) > 3
    ]
    scene.shapes.append(
        Compound(
            id="retained-body-ink",
            part="body-ink",
            label="Inchiostro conservato",
            source_region="retained-first-extraction",
            fill=trace.regions[0].color,
            stroke="none",
            loops=[p for p in loops if len(p) >= 3],
        )
    )
    for region in fills:
        scene.shapes.append(
            Compound(
                id=region.id,
                part="head" if region.id in head_regions else "body",
                label="Testa · contorni originali"
                if region.id in head_regions
                else "Contorni originali",
                source_region=region.id,
                fill=region.color,
                stroke="none",
                loops=region.loops,
            )
        )
    return scene
