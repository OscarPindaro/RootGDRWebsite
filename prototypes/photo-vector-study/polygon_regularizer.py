"""Deterministic, guided polygon fitting; semantic hints come from the author."""

from math import atan2, cos, hypot, sin
from typing import Literal

from pydantic import BaseModel

from study_scene import Point


class FitResult(BaseModel):
    primitive: str
    points: list[Point]
    retained_indices: list[int]
    original_vertices: int
    error_pixels: float
    relative_area_change: float


def area(points: list[Point]) -> float:
    return (
        abs(
            sum(
                a[0] * b[1] - b[0] * a[1]
                for a, b in zip(points, points[1:] + points[:1])
            )
        )
        / 2
    )


def distance(point: Point, a: Point, b: Point) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    denominator = dx * dx + dy * dy
    t = (
        max(0, min(1, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / denominator))
        if denominator
        else 0
    )
    return hypot(point[0] - a[0] - t * dx, point[1] - a[1] - t * dy)


def fit_polygon(
    points: list[Point],
    *,
    primitive: Literal["triangle", "trapezoid", "polygon"],
    sides: int | None = None,
    pinned: set[int] | None = None,
    max_error: float = 12,
    max_area_change: float = 0.2,
) -> FitResult:
    """Remove the least significant corners, retain pins, and fit parallel bases."""
    sides = {"triangle": 3, "trapezoid": 4}.get(primitive, sides)
    if sides is None or sides < 3 or sides > len(points):
        raise ValueError(
            "The requested side count must be between 3 and the input count."
        )
    pinned = pinned or set()
    if not pinned.issubset(range(len(points))) or len(pinned) > sides:
        raise ValueError("The requested primitive cannot retain all pinned corners.")
    indices = list(range(len(points)))
    while len(indices) > sides:
        candidates = [
            (
                distance(
                    points[index],
                    points[indices[i - 1]],
                    points[indices[(i + 1) % len(indices)]],
                ),
                i,
            )
            for i, index in enumerate(indices)
            if index not in pinned
        ]
        _, remove = min(candidates)
        indices.pop(remove)
    fitted = [points[i] for i in indices]
    if primitive == "triangle" and not pinned and len(points) > 3:
        # Refit the three contour runs instead of simply cutting away rounded
        # corners. Intersecting their least-squares lines avoids a shrunken crest.
        lines = []
        for i, start in enumerate(indices):
            end = indices[(i + 1) % len(indices)]
            run = (
                points[start : end + 1]
                if end > start
                else points[start:] + points[: end + 1]
            )
            x, y = (sum(p[j] for p in run) / len(run) for j in (0, 1))
            xx = sum((p[0] - x) ** 2 for p in run)
            yy = sum((p[1] - y) ** 2 for p in run)
            xy = sum((p[0] - x) * (p[1] - y) for p in run)
            angle = atan2(2 * xy, xx - yy) / 2
            a, b = -sin(angle), cos(angle)
            lines.append((a, b, a * x + b * y))
        candidate = []
        for i in range(3):
            a, b, c = lines[i - 1]
            d, e, f = lines[i]
            determinant = a * e - b * d
            if abs(determinant) < 1e-6:
                break
            candidate.append(
                ((c * e - b * f) / determinant, (a * f - c * d) / determinant)
            )
        if len(candidate) == 3:
            fitted = candidate
    if primitive == "trapezoid":
        candidates = []
        for first in (0, 1):
            pairs = [(first, (first + 1) % 4), ((first + 2) % 4, (first + 3) % 4)]
            directions = []
            for a, b in pairs:
                dx, dy = fitted[b][0] - fitted[a][0], fitted[b][1] - fitted[a][1]
                length = hypot(dx, dy)
                if length < 1e-8:
                    break
                directions.append((dx / length, dy / length))
            if len(directions) != 2:
                continue
            if sum(a * b for a, b in zip(*directions)) < 0:
                directions[1] = tuple(-v for v in directions[1])
            x, y = (sum(d[j] for d in directions) for j in (0, 1))
            norm = hypot(x, y)
            direction = x / norm, y / norm
            candidate = fitted.copy()
            feasible = True
            for a, b in pairs:
                dx, dy = fitted[b][0] - fitted[a][0], fitted[b][1] - fitted[a][1]
                projection = dx * direction[0] + dy * direction[1]
                vector = projection * direction[0], projection * direction[1]
                if indices[a] in pinned and indices[b] in pinned:
                    feasible &= abs(dx * direction[1] - dy * direction[0]) < 1e-7
                elif indices[a] in pinned:
                    candidate[b] = (fitted[a][0] + vector[0], fitted[a][1] + vector[1])
                elif indices[b] in pinned:
                    candidate[a] = (fitted[b][0] - vector[0], fitted[b][1] - vector[1])
                else:
                    midpoint = (
                        (fitted[a][0] + fitted[b][0]) / 2,
                        (fitted[a][1] + fitted[b][1]) / 2,
                    )
                    candidate[a] = (
                        midpoint[0] - vector[0] / 2,
                        midpoint[1] - vector[1] / 2,
                    )
                    candidate[b] = (
                        midpoint[0] + vector[0] / 2,
                        midpoint[1] + vector[1] / 2,
                    )
            if feasible:
                change = sum(
                    (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2
                    for a, b in zip(candidate, fitted)
                )
                candidates.append((change, candidate))
        if not candidates:
            raise ValueError("Parallel bases conflict with pinned corners.")
        fitted = min(candidates, key=lambda item: item[0])[1]
    # Symmetric vertex-to-boundary error exposes removed notches as well as drift.
    error = max(
        max(
            min(distance(p, a, b) for a, b in zip(target, target[1:] + target[:1]))
            for p in source
        )
        for source, target in ((points, fitted), (fitted, points))
    )
    relative = abs(area(fitted) - area(points)) / max(area(points), 1e-8)
    if error > max_error or relative > max_area_change:
        raise ValueError(
            f"Fit would lose too much detail: {error:.2f}px boundary error, {relative:.1%} area change."
        )
    return FitResult(
        primitive=primitive,
        points=fitted,
        retained_indices=indices,
        original_vertices=len(points),
        error_pixels=error,
        relative_area_change=relative,
    )
