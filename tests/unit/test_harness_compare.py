"""Unit tests for the prototype map used by `harness compare`."""

from __future__ import annotations

import pytest

from harness.commands.compare import MAP_FILE, PROTOTYPE_DIR, _load_map, _prototype_for


def test_map_resolves_the_main_pages() -> None:
    prototype_map = _load_map(MAP_FILE)

    assert _prototype_for("/worlds", prototype_map).prototype == "index.html"
    assert _prototype_for("/worlds/abc", prototype_map).prototype == "mondo.html"
    assert (
        _prototype_for("/worlds/abc/characters", prototype_map).prototype
        == "personaggi.html"
    )
    assert (
        _prototype_for("/worlds/abc/characters/xyz", prototype_map).prototype
        == "personaggio.html"
    )
    assert (
        _prototype_for("/worlds/abc/places", prototype_map).prototype == "luoghi.html"
    )
    assert (
        _prototype_for("/worlds/abc/places/xyz", prototype_map).prototype
        == "luogo.html"
    )


def test_map_rejects_unmapped_paths() -> None:
    prototype_map = _load_map(MAP_FILE)

    with pytest.raises(ValueError, match="no prototype mapped"):
        _prototype_for("/settings", prototype_map)


def test_every_mapped_prototype_exists() -> None:
    prototype_map = _load_map(MAP_FILE)

    missing = [
        entry.prototype
        for entry in prototype_map.entries
        if not (PROTOTYPE_DIR / entry.prototype).is_file()
    ]
    assert missing == []
