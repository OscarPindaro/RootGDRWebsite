"""Unit tests for the structural (landmark) comparison and its gate."""

from harness.test.landmarks import (
    ElementMetrics,
    Landmark,
    LandmarkIssue,
    LandmarkMeasurement,
    PageMetrics,
    structural_failures,
    structural_issues,
)


def _element(
    selector: str = ".face",
    *,
    x=0.0,
    y=0.0,
    width=200.0,
    height=56.0,
    font="IBM Plex Sans",
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


def _ok(selector: str = ".face", **kwargs) -> LandmarkMeasurement:
    return LandmarkMeasurement(
        selector=selector,
        matches=1,
        visible=True,
        offscreen=False,
        metrics=_element(selector, **kwargs),
    )


def _page(**landmarks: LandmarkMeasurement) -> PageMetrics:
    return PageMetrics(scroll_width=1440, client_width=1440, landmarks=dict(landmarks))


LANDMARKS = {"face": Landmark(app=".face", prototype=".face")}


def _issues(
    app: PageMetrics, prototype: PageMetrics, *, viewport="desktop", landmarks=None
):
    return structural_issues(
        app,
        prototype,
        landmarks or LANDMARKS,
        route="/worlds/x",
        viewport=viewport,
    )


def _rendered(issues: list[LandmarkIssue]) -> list[str]:
    return [issue.render() for issue in issues]


def test_identical_pages_produce_no_issues() -> None:
    app = _page(face=_ok())
    prototype = _page(face=_ok())
    assert _issues(app, prototype) == []


def test_width_divergence_is_geometry_and_never_gates() -> None:
    app = _page(face=_ok(width=320))
    prototype = _page(face=_ok(width=240))
    issues = _issues(app, prototype)
    assert _rendered(issues) == ["face: width: app 320px, prototype 240px (+80px)"]
    assert structural_failures(issues) == []


def test_vertical_shift_and_font_stay_geometry() -> None:
    app = _page(face=_ok(y=310, font="Georgia, serif"))
    prototype = _page(face=_ok(y=0))
    issues = _issues(app, prototype)
    assert _rendered(issues) == [
        "face: y differs by 310px: app is below prototype",
        "face: font family differs",
    ]
    assert structural_failures(issues) == []


def test_page_overflow_is_reported_per_side() -> None:
    app = _page(face=_ok())
    app.scroll_width = 411
    app.client_width = 390
    issues = _issues(app, _page(face=_ok()))
    assert issues[0].side == "app" and "page overflow" in issues[0].detail


def test_a_stale_selector_is_a_missing_failure() -> None:
    app = _page(
        face=LandmarkMeasurement(
            selector=".face", matches=0, visible=False, offscreen=False
        )
    )
    issues = _issues(app, _page(face=_ok()))
    assert len(issues) == 1
    issue = issues[0]
    assert (issue.kind, issue.side, issue.selector) == ("missing", "app", ".face")
    assert issue.route == "/worlds/x" and issue.viewport == "desktop"
    assert structural_failures(issues) == issues


def test_an_ambiguous_selector_is_a_failure() -> None:
    app = _page(face=_ok())
    app.landmarks["face"] = LandmarkMeasurement(
        selector=".face", matches=3, visible=True, offscreen=False, metrics=_element()
    )
    issues = _issues(app, _page(face=_ok()))
    assert [issue.kind for issue in issues] == ["ambiguous"]
    assert issues[0].detail == "selector matches 3 elements"
    assert structural_failures(issues) == issues


def test_a_hidden_landmark_fails_unless_declared_hidden_on_that_viewport() -> None:
    hidden = LandmarkMeasurement(
        selector=".rail",
        matches=1,
        visible=False,
        offscreen=False,
        metrics=_element(".rail"),
    )
    app = _page(rail=hidden)
    prototype = _page(rail=hidden)
    landmarks = {"rail": Landmark(app=".rail", prototype=".rail")}

    desktop = _issues(app, prototype, landmarks=landmarks)
    assert [issue.kind for issue in desktop] == ["hidden", "hidden"]
    assert structural_failures(desktop) == desktop

    phone_landmarks = {
        "rail": Landmark(app=".rail", prototype=".rail", hidden_on=["phone"])
    }
    assert _issues(app, prototype, viewport="phone", landmarks=phone_landmarks) == []


def test_a_closed_drawer_offscreen_is_allowed_only_when_declared() -> None:
    offscreen = LandmarkMeasurement(
        selector=".rail",
        matches=1,
        visible=True,
        offscreen=True,
        metrics=_element(".rail"),
    )
    app = _page(rail=offscreen)
    prototype = _page(rail=offscreen)
    landmarks = {"rail": Landmark(app=".rail", prototype=".rail", hidden_on=["phone"])}
    issues = _issues(app, prototype, viewport="phone", landmarks=landmarks)
    assert issues == []

    desktop = _issues(app, prototype, landmarks=landmarks)
    assert [issue.detail for issue in desktop] == [
        "landmark is offscreen",
        "landmark is offscreen",
    ]


def test_optional_viewports_allow_a_missing_landmark() -> None:
    landmarks = {
        "quick_strip": Landmark(
            app=".grid-flush", prototype=".grid--quick", optional_on=["phone"]
        )
    }
    app = _page(
        quick_strip=LandmarkMeasurement(
            selector=".grid-flush", matches=0, visible=False, offscreen=False
        )
    )
    prototype = _page(
        quick_strip=LandmarkMeasurement(
            selector=".grid--quick", matches=0, visible=False, offscreen=False
        )
    )
    assert _issues(app, prototype, viewport="phone", landmarks=landmarks) == []
    assert len(_issues(app, prototype, landmarks=landmarks)) == 2


def test_phone_touch_targets_are_geometry_only() -> None:
    app = _page(face=_ok(width=36, height=32))
    prototype = _page(face=_ok(width=36, height=32))
    phone = _issues(app, prototype, viewport="phone")
    assert any("touch target" in issue.detail for issue in phone)
    assert structural_failures(phone) == []
