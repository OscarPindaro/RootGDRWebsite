"""The document bar keeps status badges out of the action buttons."""

from pathlib import Path

from backend.jinja import get_catalog

COMPONENTS_DIR = Path(__file__).parents[3] / "src" / "frontend" / "components"


def test_badge_sits_with_the_eyebrow_not_among_the_actions() -> None:
    html = str(
        get_catalog(str(COMPONENTS_DIR), app_name="Root GDR").render(
            "editorial.Docbar",
            base="/worlds/w/places/p",
            eyebrow="Luogo",
            can_manage=True,
            badge="Scena corrente",
            content='<button class="btn">Elimina</button>',
        )
    )

    lead = html.split('class="docbar__lead"', 1)[1].split("</div>", 1)[0]
    actions = html.split('class="docbar__actions"', 1)[1]

    assert "Scena corrente" in lead
    assert "Scena corrente" not in actions


def test_without_a_badge_the_lead_only_has_the_eyebrow() -> None:
    html = str(
        get_catalog(str(COMPONENTS_DIR), app_name="Root GDR").render(
            "editorial.Docbar",
            base="/worlds/w/places/p",
            eyebrow="Luogo",
            can_manage=False,
        )
    )

    assert 'class="pill pill-forest"' not in html
