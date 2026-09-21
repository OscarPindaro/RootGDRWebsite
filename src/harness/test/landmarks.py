"""Structural (DOM/geometry) comparison alongside the pixel diff.

The pixel percentage says how much two screenshots differ, not why. The
landmark extraction measures a small set of semantic elements — rail,
container, masthead, document face, … — on both sides and reports divergences
in geometry and typography, so a data difference can be told apart from a
structural one.
"""

from __future__ import annotations

from pydantic import BaseModel

_TOUCH_TARGET = 44.0
_POSITION_TOLERANCE = 8.0

# Evaluated in the live page: page-level overflow plus one entry per landmark.
MEASURE_JS = """
(selectors) => {
  const measure = (selector) => {
    const element = document.querySelector(selector);
    if (!element) return null;
    const rect = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    return {
      x: rect.x, y: rect.y, width: rect.width, height: rect.height,
      display: style.display,
      font_family: style.fontFamily,
      font_size: style.fontSize,
      line_height: style.lineHeight,
      gap: style.gap,
      padding: style.padding,
      border_width: style.borderWidth,
      overflow_x: style.overflowX,
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


class PageMetrics(BaseModel):
    scroll_width: int
    client_width: int
    landmarks: dict[str, ElementMetrics]


class Landmark(BaseModel):
    """One semantic landmark, mapped between app and prototype."""

    app: str
    prototype: str
    tolerance_px: float = 2.0


def structural_diagnostics(
    app: PageMetrics,
    prototype: PageMetrics,
    landmarks: dict[str, Landmark],
    *,
    phone: bool = False,
) -> list[str]:
    """Human-readable structural differences; empty when the sides match."""
    issues: list[str] = []
    for label, metrics in (("app", app), ("prototype", prototype)):
        if metrics.scroll_width > metrics.client_width:
            issues.append(
                f"page overflow ({label}): scrollWidth {metrics.scroll_width} "
                f"> clientWidth {metrics.client_width}"
            )
    for name, landmark in landmarks.items():
        app_element = app.landmarks.get(name)
        prototype_element = prototype.landmarks.get(name)
        if app_element is None:
            issues.append(f"{name}: landmark missing in app")
            continue
        if prototype_element is None:
            issues.append(f"{name}: landmark missing in prototype")
            continue
        width_delta = app_element.width - prototype_element.width
        if abs(width_delta) > landmark.tolerance_px:
            issues.append(
                f"{name}.width: app {app_element.width:.0f}px, "
                f"prototype {prototype_element.width:.0f}px ({width_delta:+.0f}px)"
            )
        y_delta = app_element.y - prototype_element.y
        if abs(y_delta) > max(landmark.tolerance_px, _POSITION_TOLERANCE):
            issues.append(
                f"{name}.y differs by {abs(y_delta):.0f}px: "
                f"app is {'below' if y_delta > 0 else 'above'} prototype"
            )
        if _font(app_element) != _font(prototype_element):
            issues.append(f"{name}: font family differs")
        if phone and min(app_element.width, app_element.height) < _TOUCH_TARGET:
            issues.append(
                f"touch target below 44px: {name} "
                f"{app_element.width:.0f}x{app_element.height:.0f}"
            )
    return issues


def _font(element: ElementMetrics) -> str:
    return " ".join(element.font_family.lower().split())
