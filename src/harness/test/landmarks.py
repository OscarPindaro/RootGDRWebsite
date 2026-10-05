"""Structural (DOM/geometry) comparison alongside the pixel diff.

The pixel percentage says how much two screenshots differ, not why. The
landmark extraction measures a small set of semantic elements — rail,
container, masthead, document face, … — on both sides, counts matches and
records whether the element is rendered and on-screen. Missing, ambiguous or
unexpectedly hidden landmarks are mapping defects and can gate a comparison;
geometry and typography differences stay diagnostics.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

_TOUCH_TARGET = 44.0
_POSITION_TOLERANCE = 8.0

# Evaluated in the live page: page-level overflow plus one entry per landmark.
# `offscreen` means the element sits entirely outside the viewport on the
# negative side (a closed drawer), not merely below the fold.
MEASURE_JS = """
(selectors) => {
  const measure = (selector) => {
    const matches = document.querySelectorAll(selector);
    if (matches.length === 0) {
      return {matches: 0, visible: false, offscreen: false, metrics: null};
    }
    const element = matches[0];
    const rect = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    const visible = rect.width > 0 && rect.height > 0 &&
      style.display !== "none" && style.visibility !== "hidden";
    const offscreen = rect.right <= 0 || rect.bottom <= 0 ||
      rect.left >= document.documentElement.clientWidth;
    return {
      matches: matches.length,
      visible,
      offscreen,
      metrics: {
        x: rect.x, y: rect.y, width: rect.width, height: rect.height,
        display: style.display,
        font_family: style.fontFamily,
        font_size: style.fontSize,
        line_height: style.lineHeight,
        gap: style.gap,
        padding: style.padding,
        border_width: style.borderWidth,
        overflow_x: style.overflowX,
      },
    };
  };
  const landmarks = {};
  for (const [name, selector] of Object.entries(selectors)) {
    landmarks[name] = measure(selector);
  }
  return {
    scroll_width: document.documentElement.scrollWidth,
    client_width: document.documentElement.clientWidth,
    landmarks,
  };
}
"""


class ElementMetrics(BaseModel):
    selector: str
    x: float
    y: float
    width: float
    height: float
    display: str
    font_family: str
    font_size: str
    line_height: str
    gap: str
    padding: str
    border_width: str
    overflow_x: str


class LandmarkMeasurement(BaseModel):
    """What one selector resolved to in one rendered page."""

    selector: str
    matches: int
    visible: bool
    offscreen: bool
    metrics: ElementMetrics | None = None


class PageMetrics(BaseModel):
    scroll_width: int
    client_width: int
    landmarks: dict[str, LandmarkMeasurement]


class Landmark(BaseModel):
    """One semantic landmark, mapped between app and prototype.

    ``optional_on`` lists viewports where the landmark may be absent;
    ``hidden_on`` lists viewports where it may be hidden or offscreen (for
    example a phone rail that is closed by design).
    """

    app: str
    prototype: str
    tolerance_px: float = 2.0
    optional_on: list[str] = []
    hidden_on: list[str] = []


IssueKind = Literal["missing", "ambiguous", "hidden", "geometry"]


class LandmarkIssue(BaseModel):
    """One structural finding, located enough to fix the mapping."""

    route: str
    viewport: str
    landmark: str
    side: Literal["app", "prototype"] | None = None
    selector: str = ""
    kind: IssueKind
    detail: str

    def render(self) -> str:
        location = f" {self.side} ({self.selector})" if self.side else ""
        return f"{self.landmark}{location}: {self.detail}"


def measure_landmarks(page, selectors: dict[str, str]) -> PageMetrics:
    """Run MEASURE_JS on a rendered page and type the result."""
    raw = page.evaluate(MEASURE_JS, selectors)
    landmarks: dict[str, LandmarkMeasurement] = {}
    for name, measurement in raw["landmarks"].items():
        selector = selectors[name]
        metrics = measurement["metrics"]
        landmarks[name] = LandmarkMeasurement(
            selector=selector,
            matches=measurement["matches"],
            visible=measurement["visible"],
            offscreen=measurement["offscreen"],
            metrics=(
                None
                if metrics is None
                else ElementMetrics.model_validate({**metrics, "selector": selector})
            ),
        )
    return PageMetrics(
        scroll_width=raw["scroll_width"],
        client_width=raw["client_width"],
        landmarks=landmarks,
    )


def structural_issues(
    app: PageMetrics,
    prototype: PageMetrics,
    landmarks: dict[str, Landmark],
    *,
    route: str,
    viewport: str,
) -> list[LandmarkIssue]:
    """Typed structural findings for one route and viewport."""
    issues: list[LandmarkIssue] = []
    for label, metrics in (("app", app), ("prototype", prototype)):
        if metrics.scroll_width > metrics.client_width:
            issues.append(
                LandmarkIssue(
                    route=route,
                    viewport=viewport,
                    landmark="page",
                    side=label,
                    kind="geometry",
                    detail=(
                        f"page overflow: scrollWidth {metrics.scroll_width} "
                        f"> clientWidth {metrics.client_width}"
                    ),
                )
            )
    for name, landmark in landmarks.items():
        for side, metrics, selector in (
            ("app", app, landmark.app),
            ("prototype", prototype, landmark.prototype),
        ):
            measurement = metrics.landmarks.get(name)
            if measurement is None or measurement.matches == 0:
                if viewport not in landmark.optional_on:
                    issues.append(
                        LandmarkIssue(
                            route=route,
                            viewport=viewport,
                            landmark=name,
                            side=side,
                            selector=selector,
                            kind="missing",
                            detail="landmark missing",
                        )
                    )
                continue
            if measurement.matches > 1:
                issues.append(
                    LandmarkIssue(
                        route=route,
                        viewport=viewport,
                        landmark=name,
                        side=side,
                        selector=selector,
                        kind="ambiguous",
                        detail=f"selector matches {measurement.matches} elements",
                    )
                )
                continue
            if not measurement.visible or measurement.offscreen:
                if viewport not in landmark.hidden_on:
                    issues.append(
                        LandmarkIssue(
                            route=route,
                            viewport=viewport,
                            landmark=name,
                            side=side,
                            selector=selector,
                            kind="hidden",
                            detail=(
                                "landmark is hidden"
                                if not measurement.visible
                                else "landmark is offscreen"
                            ),
                        )
                    )
    issues.extend(_geometry_issues(app, prototype, landmarks, route, viewport))
    return issues


def _geometry_issues(
    app: PageMetrics,
    prototype: PageMetrics,
    landmarks: dict[str, Landmark],
    route: str,
    viewport: str,
) -> list[LandmarkIssue]:
    issues: list[LandmarkIssue] = []
    for name, landmark in landmarks.items():
        app_element = app.landmarks[name].metrics
        prototype_element = prototype.landmarks[name].metrics
        if app_element is None or prototype_element is None:
            continue

        def issue(detail: str) -> LandmarkIssue:
            return LandmarkIssue(
                route=route,
                viewport=viewport,
                landmark=name,
                kind="geometry",
                detail=detail,
            )

        width_delta = app_element.width - prototype_element.width
        if abs(width_delta) > landmark.tolerance_px:
            issues.append(
                issue(
                    f"width: app {app_element.width:.0f}px, "
                    f"prototype {prototype_element.width:.0f}px ({width_delta:+.0f}px)"
                )
            )
        y_delta = app_element.y - prototype_element.y
        if abs(y_delta) > max(landmark.tolerance_px, _POSITION_TOLERANCE):
            issues.append(
                issue(
                    f"y differs by {abs(y_delta):.0f}px: app is "
                    f"{'below' if y_delta > 0 else 'above'} prototype"
                )
            )
        if _font(app_element) != _font(prototype_element):
            issues.append(issue("font family differs"))
        if (
            viewport == "phone"
            and min(app_element.width, app_element.height) < _TOUCH_TARGET
        ):
            issues.append(
                issue(
                    f"touch target below 44px: {name} "
                    f"{app_element.width:.0f}x{app_element.height:.0f}"
                )
            )
    return issues


def structural_failures(issues: list[LandmarkIssue]) -> list[LandmarkIssue]:
    """The gate: mapping defects, never ordinary geometry differences."""
    return [issue for issue in issues if issue.kind != "geometry"]


def _font(element: ElementMetrics) -> str:
    return " ".join(element.font_family.lower().split())
