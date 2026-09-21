from backend.content.constants import ContentKind
from backend.content.markdown import (
    MentionTarget,
    mention_labels,
    render_markdown,
)
from backend.content.references import document_labels


def test_mention_labels_are_distinct_and_ordered() -> None:
    body = "Vedi @[Rugginosa] e @[luogo:Il Guado], poi di nuovo @[Rugginosa]."
    assert mention_labels(body) == ["Rugginosa", "luogo:Il Guado"]


def test_mention_labels_ignores_plain_at_signs() -> None:
    assert mention_labels("email a@b.co and no brackets") == []


def test_render_markdown_resolves_a_target_to_semantic_markup() -> None:
    target = MentionTarget(
        id="1",
        kind=ContentKind.PLACE,
        tint="p8",
        href="/worlds/w/places/1",
        name="Il Guado Spezzato",
    )
    html = str(
        render_markdown("Vedi @[Il Guado Spezzato].", {"Il Guado Spezzato": target})
    )
    assert 'class="mention"' in html
    assert 'data-kind="luogo"' in html
    assert 'data-color="p8"' in html
    assert 'href="/worlds/w/places/1"' in html


def test_render_markdown_marks_a_missing_reference() -> None:
    html = str(render_markdown("Vedi @[Nessuno].", {"Nessuno": None}))
    assert "mention--missing" in html
    assert "<a" not in html


def test_render_markdown_does_not_allow_raw_html() -> None:
    html = str(render_markdown("<script>alert(1)</script>", {}))
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_render_markdown_escapes_unresolved_mention_labels() -> None:
    html = str(render_markdown('@[<img src=x onerror="alert(1)">]', {}))
    assert "<img" not in html
    assert "&lt;img" in html


def test_document_labels_deduplicates_summary_and_body() -> None:
    assert document_labels(
        "Prima @[Rugginosa] e @[luogo:Il Guado].",
        "Ancora @[Rugginosa] e @[Nessuno].",
    ) == ["Rugginosa", "luogo:Il Guado", "Nessuno"]
