"""Component tests for ``editorial.ImageEditor``.

Covers the world cover proportion (it must match the world list) and the
history button position (under the image, not over it).
"""

import pytest

from backend.content.view_helpers import animal_options, tint_options

pytestmark = pytest.mark.frontend


def _props(**overrides) -> dict:
    props = {
        "world_id": "00000000-0000-0000-0000-000000000000",
        "owner_kind": "world",
        "owner_id": "00000000-0000-0000-0000-000000000001",
        "upload_url": "/api/worlds/w/characters/c/image",
        "fallback_action": "/worlds/w/characters/c/image",
        "image_url": None,
        "can_manage": True,
        "locked": False,
        "version": 3,
        "tint": "p8",
        "symbol": "🐈",
        "symbol_name": "animal",
        "symbol_kind": "emoji",
        "symbol_options": animal_options(),
        "tints": tint_options(),
    }
    props.update(overrides)
    return props


def test_world_cover_keeps_the_world_list_proportion(component):
    page = component.mount("editorial.ImageEditor", props=_props(owner_kind="world"))

    ratio = page.evaluate(
        """() => {
            const rect = document.querySelector('.image-editor__surface')
                .getBoundingClientRect();
            return rect.width / rect.height;
        }"""
    )
    assert ratio == pytest.approx(16 / 7, rel=0.05)


def test_document_face_keeps_the_vertical_proportion(component):
    page = component.mount(
        "editorial.ImageEditor", props=_props(owner_kind="character")
    )

    ratio = page.evaluate(
        """() => {
            const rect = document.querySelector('.image-editor__surface')
                .getBoundingClientRect();
            return rect.width / rect.height;
        }"""
    )
    assert ratio == pytest.approx(4 / 5, rel=0.05)


def test_history_button_sits_below_the_image(component):
    page = component.mount("editorial.ImageEditor", props=_props(owner_kind="world"))

    surface_bottom = page.evaluate(
        "() => document.querySelector('.image-editor__surface')"
        ".getBoundingClientRect().bottom"
    )
    trigger_top = page.evaluate(
        "() => document.querySelector('[data-testid=\"image-history-open\"]')"
        ".getBoundingClientRect().top"
    )
    assert trigger_top >= surface_bottom
