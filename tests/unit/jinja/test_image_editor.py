from pathlib import Path

from backend.content.view_helpers import animal_options, tint_options
from backend.jinja import get_catalog

COMPONENTS_DIR = Path(__file__).parents[3] / "src" / "frontend" / "components"


def _render(**overrides: object) -> str:
    props = {
        "world_id": "00000000-0000-0000-0000-000000000000",
        "owner_kind": "character",
        "owner_id": "00000000-0000-0000-0000-000000000001",
        "upload_url": "/api/worlds/world/characters/character/image",
        "fallback_action": "/worlds/world/characters/character/image",
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
    catalog = get_catalog(str(COMPONENTS_DIR), app_name="Root GDR")
    return str(catalog.render("editorial.ImageEditor", **props))


def test_editable_image_editor_has_progressive_upload_and_history_controls() -> None:
    html = _render()

    assert 'data-testid="image-editor-surface"' in html
    assert 'enctype="multipart/form-data"' in html
    assert 'type="file"' in html
    assert "Scegli file" not in html
    assert "Carica immagine" in html
    assert 'data-testid="image-history-dialog"' in html
    assert 'data-testid="image-history-list"' in html
    assert 'name="animal"' in html
    assert 'name="tint"' in html
    assert 'data-version="3"' in html


def test_existing_image_changes_copy_and_clear_action() -> None:
    html = _render(image_url="/api/image")

    assert "Cambia immagine" in html
    assert 'src="/api/image"' in html
    assert 'data-testid="image-clear-current"' in html


def test_readonly_image_editor_hides_every_edit_control() -> None:
    html = _render(can_manage=False)

    assert 'type="file"' not in html
    assert "Storico" not in html
    assert "Carica immagine" not in html
    assert 'name="animal"' not in html
    assert 'data-testid="image-editor-surface"' not in html
