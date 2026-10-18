"""Browser checks for the committed, standalone drawing study."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.frontend
STUDY = Path(__file__).parents[2] / "prototypes" / "photo-vector-study"


@pytest.mark.parametrize(
    "profile,width,height", [("desktop", 1440, 1000), ("phone", 390, 844)]
)
def test_shape_gallery_inspection(browser_session, profile, width, height):
    browser = browser_session.chromium.launch()
    context = browser.new_context(viewport={"width": width, "height": height})
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("requestfailed", lambda request: errors.append(request.url))
    page.on(
        "console",
        lambda message: (
            errors.append(message.text) if message.type == "error" else None
        ),
    )
    try:
        page.goto((STUDY / "output/shapes/index.html").as_uri())
        assert page.locator("article").count() == 3
        assert page.locator(".interactive svg").count() == 3
        assert page.locator(".reference img").count() == 3
        assert page.evaluate(
            "Array.from(document.images).every(image => image.complete && image.naturalWidth > 0)"
        )
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        with page.expect_popup() as opened:
            page.locator(".reference a").first.click()
        original = opened.value
        original.wait_for_load_state()
        assert original.url.endswith("/references/altus.jpg")
        original.close()
        group = page.locator(".interactive svg g").first
        group.focus()
        page.keyboard.press("Enter")
        assert "selected" in (group.get_attribute("class") or "")
        before = page.locator(".interactive svg").first.get_attribute("viewBox")
        button = page.locator(".explode").first
        button.click()
        assert button.get_attribute("aria-pressed") == "true"
        assert group.get_attribute("transform").startswith("translate(")
        button.click()
        assert button.get_attribute("aria-pressed") == "false"
        assert group.get_attribute("transform") == ""
        assert page.locator(".interactive svg").first.get_attribute("viewBox") == before
        group.evaluate("element => element.classList.remove('selected')")
        page.locator("body").click(position={"x": 5, "y": 5})
        screenshots = Path("/tmp/photo-vector-study-checks")
        screenshots.mkdir(exist_ok=True)
        page.screenshot(path=str(screenshots / f"{profile}.png"), full_page=True)
        assert not errors
    finally:
        context.close()
        browser.close()
