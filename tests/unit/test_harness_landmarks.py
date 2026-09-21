"""Unit tests for the structural (landmark) comparison."""

from harness.test.landmarks import (
    ElementMetrics,
    Landmark,
    PageMetrics,
    structural_diagnostics,
)


def _element(
    selector: str, *, x=0.0, y=0.0, width=200.0, height=56.0, font="IBM Plex Sans"
) -> ElementMetrics:
    return ElementMetrics(
        selector=selector,
        x=x,
        y=y,
        width=width,
        height=height,
        display="flex",
        font_family=font,
        font_size="16px",
        line_height="24px",
        gap="8px",
        padding="8px",
        border_width="1px",
        overflow_x="visible",
    )


def _page(**landmarks) -> PageMetrics:
    return PageMetrics(
        scroll_width=1440,
        client_width=1440,
        landmarks=dict(landmarks),
    )


LANDMARKS = {"face": Landmark(app=".face", prototype=".face")}


def test_identical_pages_produce_no_diagnostics() -> None:
    app = _page(face=_element(".face"))
    prototype = _page(face=_element(".face"))

    assert structural_diagnostics(app, prototype, LANDMARKS) == []


def test_width_divergence_is_reported_with_direction() -> None:
    app = _page(face=_element(".face", width=320))
    prototype = _page(face=_element(".face", width=240))

    issues = structural_diagnostics(app, prototype, LANDMARKS)

    assert issues == ["face.width: app 320px, prototype 240px (+80px)"]


def test_vertical_shift_is_reported() -> None:
    app = _page(face=_element(".face", y=310))
    prototype = _page(face=_element(".face", y=0))

    issues = structural_diagnostics(app, prototype, LANDMARKS)

    assert issues == ["face.y differs by 310px: app is below prototype"]


def test_page_overflow_is_reported_per_side() -> None:
    app = _page(face=_element(".face"))
    app.scroll_width = 411
    app.client_width = 390
    prototype = _page(face=_element(".face"))

    issues = structural_diagnostics(app, prototype, LANDMARKS)

    assert "page overflow (app): scrollWidth 411 > clientWidth 390" in issues


def test_missing_landmark_is_reported() -> None:
    app = _page()
    prototype = _page(face=_element(".face"))

    issues = structural_diagnostics(app, prototype, LANDMARKS)

    assert issues == ["face: landmark missing in app"]


def test_font_family_difference_is_reported() -> None:
    app = _page(face=_element(".face", font="Georgia, serif"))
    prototype = _page(face=_element(".face"))

    issues = structural_diagnostics(app, prototype, LANDMARKS)

    assert issues == ["face: font family differs"]


def test_phone_reports_small_touch_targets() -> None:
    landmarks = {"face": Landmark(app=".face", prototype=".face")}
    app = _page(face=_element(".face", width=36, height=32))
    prototype = _page(face=_element(".face", width=36, height=32))

    phone_issues = structural_diagnostics(app, prototype, landmarks, phone=True)
    desktop_issues = structural_diagnostics(app, prototype, landmarks)

    assert "touch target below 44px: face 36x32" in phone_issues
    assert not any("touch target" in issue for issue in desktop_issues)
