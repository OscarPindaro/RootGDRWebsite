"""The committed reference world is a valid bundle with the expected shape."""

from __future__ import annotations

from pathlib import Path

import yaml

from src.backend.content.bulk import WorldBundle
from src.backend.stories.models import StoryStatus

BUNDLE = Path(__file__).parents[2] / "seed" / "boschetto-di-smeraldo.yaml"


def _bundle() -> WorldBundle:
    return WorldBundle.model_validate(
        yaml.safe_load(BUNDLE.read_text(encoding="utf-8"))
    )


def test_bundle_parses_and_names_the_current_place() -> None:
    bundle = _bundle()

    assert bundle.world.name == "Il Boschetto di Smeraldo"
    assert bundle.world.current_place == "Radura della Grande Quercia"
    assert any(place.name == bundle.world.current_place for place in bundle.places)


def test_bundle_covers_every_content_type() -> None:
    bundle = _bundle()
    published = [character for character in bundle.characters if not character.is_draft]

    assert [character.animal for character in published] == ["🐈", "🦊", "🐁", "🦡"]
    assert any(character.is_draft for character in bundle.characters)
    assert len(bundle.npcs) == 3
    assert len(bundle.places) == 3
    assert len(bundle.sessions) == 3
    assert len(bundle.pages) == 2
    assert [story.status for story in bundle.stories] == [StoryStatus.OPEN]
    assert bundle.stories[0].session_titles


def test_bundle_bodies_use_references() -> None:
    bundle = _bundle()
    bodies = [character.body for character in bundle.characters]
    bodies += [session.body for session in bundle.sessions]

    assert any("@[" in body for body in bodies)
