"""Real-DOM landmark measurement (REQ-0011/T02).

The synthetic page reproduces the cases the gate must tell apart: a unique
element, an ambiguous selector, a hidden element, a closed drawer translated
off-screen, an element below the fold, and a stale selector.
"""

from harness.test.landmarks import measure_landmarks


def test_measure_landmarks_counts_matches_and_tells_offscreen_apart(
    browser_session,
) -> None:
    browser = browser_session.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 800, "height": 600})
    try:
        page.set_content(
            """
            <div class="one" style="width: 100px; height: 40px"></div>
            <div class="one" style="width: 100px; height: 40px"></div>
            <div class="hidden" style="display: none">x</div>
            <div class="drawer"
                 style="width: 200px; height: 300px; transform: translateX(-260px)">
              drawer
            </div>
            <div class="below"
                 style="width: 100px; height: 40px; margin-top: 2000px"></div>
            """
        )
        metrics = measure_landmarks(
            page,
            {
                "unique": ".one",
                "hidden": ".hidden",
                "drawer": ".drawer",
                "below": ".below",
                "absent": ".missing",
            },
        )
    finally:
        page.close()
        browser.close()

    assert metrics.landmarks["unique"].matches == 2
    assert metrics.landmarks["hidden"].visible is False
    assert metrics.landmarks["drawer"].visible is True
    assert metrics.landmarks["drawer"].offscreen is True
    assert metrics.landmarks["below"].visible is True
    assert metrics.landmarks["below"].offscreen is False
    assert metrics.landmarks["absent"].matches == 0
    assert metrics.landmarks["absent"].metrics is None
    assert metrics.landmarks["unique"].metrics is not None
