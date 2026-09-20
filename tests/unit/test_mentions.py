from backend.content.constants import ContentKind
from backend.content.markdown import (
    MentionTarget,
    mention_labels,
    render_markdown,
)


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
        href="/worlds/w/luoghi/1",
        name="Il Guado Spezzato",
    )
    html = str(
        render_markdown("Vedi @[Il Guado Spezzato].", {"Il Guado Spezzato": target})
    )
    assert 'class="mention"' in html
    assert 'data-kind="luogo"' in html
    assert 'data-color="p8"' in html
    assert 'href="/worlds/w/luoghi/1"' in html


def test_render_markdown_marks_a_missing_reference() -> None:
    html = str(render_markdown("Vedi @[Nessuno].", {"Nessuno": None}))
    assert "mention--missing" in html
    assert "<a" not in html


def test_render_markdown_does_not_allow_raw_html() -> None:
    html = str(render_markdown("<script>alert(1)</script>", {}))
    assert "<script>" not in html
