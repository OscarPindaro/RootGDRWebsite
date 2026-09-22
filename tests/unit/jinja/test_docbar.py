"""The document bar separates facts from commands.

``editorial.Docbar`` has a status region — eyebrow, publication, ownership, the
current scene — and a command region — edit, lock, publish, the caller's
document command, delete. The acceptance is literal: no status pill is a child
of the command region, and every command keeps the same place and treatment on
every document.
"""

import re
from pathlib import Path

from backend.jinja import get_catalog

COMPONENTS_DIR = Path(__file__).parents[3] / "src" / "frontend" / "components"

DETAILS = (
    "pages/characters/CharacterDetail.jinja",
    "pages/npcs/NpcDetail.jinja",
    "pages/places/PlaceDetail.jinja",
    "pages/sessions/SessionDetail.jinja",
    "pages/stories/StoryDetail.jinja",
    "pages/pages/PageDetail.jinja",
)


def _render(**kwargs) -> str:
    return str(
        get_catalog(str(COMPONENTS_DIR), app_name="Root GDR").render(
            "editorial.Docbar", base="/worlds/w/characters/c", **kwargs
        )
    )


def _region(html: str, region: str) -> str:
    """The inner HTML of one region; regions contain no nested div."""
    return html.split(f'class="docbar__{region}"', 1)[1].split("</div>", 1)[0]


def test_a_published_document_shows_the_fact_and_its_commands() -> None:
    html = _render(eyebrow="Personaggio", is_draft=False, can_manage=True)

    status = _region(html, "status")
    commands = _region(html, "commands")

    assert "Personaggio" in status
    assert "Pubblicato" in status
    assert "document-edit" in commands
    assert "document-lock" in commands
    assert "document-publication" in commands
    assert "document-delete" in commands
    assert "document-cancel-draft" not in commands


def test_a_draft_document_shows_bozza_and_offers_cancel() -> None:
    html = _render(eyebrow="Luogo", is_draft=True, can_manage=True)

    status = _region(html, "status")
    commands = _region(html, "commands")

    assert "Bozza" in status
    assert "Pubblicato" not in status
    assert "document-cancel-draft" in commands
    assert "document-delete" not in commands


def test_no_status_pill_is_a_child_of_the_command_region() -> None:
    html = _render(
        eyebrow="Luogo",
        is_draft=False,
        can_manage=True,
        owner_label="Giocato da Ada",
        badge="Scena corrente",
        _content='<button class="btn">Scena corrente</button>',
    )

    commands = _region(html, "commands")
    status = _region(html, "status")

    assert 'class="pill' not in commands
    # Every fact stays in the status region.
    assert "Pubblicato" in status
    assert "Giocato da Ada" in status
    assert "Scena corrente" in status


def test_a_locked_document_keeps_the_lock_toggle_and_drops_edit() -> None:
    html = _render(eyebrow="NPC", locked=True, can_manage=True)

    commands = _region(html, "commands")
    assert "document-edit" not in commands
    assert "document-lock" in commands
    assert "Bloccato" in commands
    assert 'aria-pressed="true"' in commands


def test_a_non_manager_sees_the_facts_but_no_commands() -> None:
    html = _render(
        eyebrow="Personaggio",
        is_draft=False,
        can_manage=False,
        owner_label="Giocato da Ada",
    )

    assert "docbar__commands" not in html
    assert "Giocato da Ada" in _region(html, "status")


def test_the_caller_command_lands_in_the_command_region() -> None:
    html = _render(
        eyebrow="Luogo",
        can_manage=True,
        _content=(
            '<button class="btn" data-testid="document-current">Scena corrente</button>'
        ),
    )

    commands = _region(html, "commands")
    assert "document-current" in commands
    # The shared commands precede it; delete follows it.
    assert commands.index("document-publication") < commands.index("document-current")
    assert commands.index("document-current") < commands.index("document-delete")


def test_every_command_asks_the_confirmation_endpoint() -> None:
    html = _render(eyebrow="Personaggio", is_draft=False, can_manage=True)

    assert "/confirm/delete" in html
    assert 'hx-target="#docbar-confirm"' in html
    assert 'id="docbar-confirm"' in html


def test_no_caller_passes_a_pill_into_the_docbar() -> None:
    """The acceptance, on the real documents: a pill never enters the bar's slot."""
    block = re.compile(r"<editorial\.Docbar\b.*?(?:/>|</editorial\.Docbar>)", re.DOTALL)
    for name in DETAILS:
        source = (COMPONENTS_DIR / name).read_text(encoding="utf-8")
        matched = block.search(source)
        assert matched is not None, name
        assert "<common.Pill" not in matched.group(), name
