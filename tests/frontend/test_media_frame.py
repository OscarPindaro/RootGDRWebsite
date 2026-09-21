"""Component tests for ``common.MediaFrame``.

The frame is the single place that decides an image's aspect ratio and crop.
These tests pin that, and pin that the caller's own class and style survive.
"""

import pytest

pytestmark = pytest.mark.frontend


def _mount(component, **overrides):
    props = {
        "ratio": "square",
        "src": "/static/img/plate-1.svg",
        "alt": "",
        "style": "width: 200px",
    }
    props.update(overrides)
    return component.mount("common.MediaFrame", props=props)


def test_square_ratio_is_square(component):
    page = _mount(component, ratio="square")

    box = page.locator(".media-frame").bounding_box()
    assert box is not None
    assert box["width"] == pytest.approx(box["height"], rel=0.01)


def test_portrait_ratio_is_taller_than_wide(component):
    page = _mount(component, ratio="portrait")

    box = page.locator(".media-frame").bounding_box()
    assert box is not None
    assert box["height"] == pytest.approx(box["width"] * 5 / 4, rel=0.01)


def test_landscape_ratio_is_wider_than_tall(component):
    page = _mount(component, ratio="landscape")

    box = page.locator(".media-frame").bounding_box()
    assert box is not None
    assert box["width"] == pytest.approx(box["height"] * 16 / 10, rel=0.01)


def test_the_image_is_cropped_to_fill(component):
    page = _mount(component)

    fit = page.locator(".media-frame__image").evaluate(
        "el => getComputedStyle(el).objectFit"
    )
    assert fit == "cover"


def test_the_caller_class_and_style_survive(component):
    page = _mount(component, **{"class": "cover__media"})

    frame = page.locator(".media-frame")
    classes = frame.get_attribute("class")
    assert "cover__media" in classes
    assert "media-frame--square" in classes
    assert frame.evaluate("el => getComputedStyle(el).width") == "200px"


def test_content_is_rendered_over_the_image(component):
    page = component.mount(
        "common.MediaFrame",
        props={"ratio": "landscape", "src": "/static/img/plate-1.svg", "alt": ""},
        content='<span class="cover__badge">Volume 1</span>',
    )

    assert page.locator(".cover__badge").count() == 1


def test_without_a_source_only_the_content_is_rendered(component):
    page = component.mount(
        "common.MediaFrame",
        props={"ratio": "square"},
        content="<span>placeholder</span>",
    )

    assert page.locator(".media-frame__image").count() == 0
    assert page.locator("text=placeholder").count() == 1
