"""The "@" menu and the in-editor mention use the app skin, not the defaults.

The rendered reference is ``.mention``; the mention while writing is
``.cm-lp-mention`` and the suggestion menu is CodeMirror's autocomplete
(``.cm-tooltip-autocomplete``). Neither can be exercised without a browser, so
this guards the wiring: the rules live in the reference stylesheet, the kind
travels from the mention text to the decoration, and the reading and writing
states read the same ``--mention-*`` tokens so they cannot drift.

The weight is a deliberate decision, not a detail: a mention reads as a link
inside a sentence, so the padding, radius and font weight are pinned here.
"""

from pathlib import Path

ROOT = Path(__file__).parents[2]
MAIN_CSS = (ROOT / "src/frontend/static/css/main.css").read_text()
REFERENCE_CSS = (ROOT / "src/frontend/components/editorial/Reference.css").read_text()
EDITOR_JS = (ROOT / "src/frontend/js/editor/index.js").read_text()
LIVE_PREVIEW = (ROOT / "src/frontend/js/editor/live-preview.js").read_text()

# The geometry both states read. ``--mention-bg``/``--mention-ring`` are shared
# too: the rendered pill tints them with ``--c`` and the editor keeps the
# neutral ink value.
SHARED_TOKENS = (
    "--mention-pad",
    "--mention-gap",
    "--mention-icon",
    "--mention-radius",
    "--mention-weight",
    "--mention-bg",
    "--mention-bg-hover",
    "--mention-ring",
)

KINDS = ("personaggio", "npc", "luogo", "sessione", "storia", "pagina")


def test_the_mention_rules_have_one_owner() -> None:
    # The rendered reference is an editorial concept; its rules left the global
    # stylesheet for the stylesheet the document components declare.
    assert ".mention {" not in MAIN_CSS
    assert ".cm-tooltip.cm-tooltip-autocomplete" not in MAIN_CSS
    assert ".mention {" in REFERENCE_CSS
    assert ".cm-tooltip.cm-tooltip-autocomplete" in REFERENCE_CSS


def test_the_shared_tokens_have_one_source() -> None:
    for token in SHARED_TOKENS:
        assert f"{token}:" in MAIN_CSS, f"{token} must be declared once in main.css"
        assert f"{token}:" not in REFERENCE_CSS, f"{token} is a token, not a literal"


def test_the_rendered_and_edited_mention_read_the_same_tokens() -> None:
    # Every shared token is read by the rendered rule and by the CodeMirror
    # theme, so the two states cannot drift.
    for token in (
        "--mention-pad",
        "--mention-gap",
        "--mention-radius",
        "--mention-weight",
        "--mention-bg",
        "--mention-ring",
    ):
        assert f"var({token})" in REFERENCE_CSS, f"the rendered pill must read {token}"
        assert f"var({token})" in EDITOR_JS, f"the editor theme must read {token}"
    assert "var(--mention-icon)" in REFERENCE_CSS


def test_the_weight_is_reduced_and_pinned() -> None:
    assert "--mention-pad: 0.02em 0.25em;" in MAIN_CSS
    assert "--mention-gap: 0.25em;" in MAIN_CSS
    assert "--mention-icon: 0.8em;" in MAIN_CSS
    assert "--mention-radius: var(--radius-sm);" in MAIN_CSS
    assert "--mention-weight: var(--weight-regular);" in MAIN_CSS
    # The old chip: a 5px corner, a 500 weight and a literal background in the
    # CodeMirror theme. None may come back.
    assert "border-radius: 5px" not in REFERENCE_CSS
    assert "font-weight: 500" not in REFERENCE_CSS
    assert "rgba(23, 21, 15, 0.06)" not in EDITOR_JS
    assert '"5px"' not in EDITOR_JS
    assert '"500"' not in EDITOR_JS


def test_the_negative_inline_margin_is_gone() -> None:
    # It crowded the words on either side; the pill sits in the sentence now.
    assert "margin: 0 -0.1em" not in REFERENCE_CSS
    assert "-0.1em" not in REFERENCE_CSS


def test_the_reference_keeps_its_semantic_identity() -> None:
    # Tint.
    for index in range(1, 13):
        assert f'.mention[data-color="p{index}"]' in REFERENCE_CSS
    # Kind icon, drawn in CSS, for both the rendered pill and the editor.
    assert ".mention::before" in REFERENCE_CSS
    assert ".cm-lp-mention[data-kind]::before" in REFERENCE_CSS
    for kind in KINDS:
        assert f'.mention[data-kind="{kind}"]' in REFERENCE_CSS
        assert f'.cm-lp-mention[data-kind="{kind}"]' in REFERENCE_CSS
    # The editor tags the mention with its kind so the pill can show the icon.
    assert 'attributes: { "data-kind": kind }' in LIVE_PREVIEW
    assert '"data-kind"' in LIVE_PREVIEW


def test_the_missing_reference_and_hidden_states_survive() -> None:
    assert ".mention--missing {" in REFERENCE_CSS
    assert "background: transparent" in REFERENCE_CSS
    assert "cursor: help" in REFERENCE_CSS
    assert ".mention--missing::before { display: none; }" in REFERENCE_CSS
    assert ".mention-hidden { display: none; }" in REFERENCE_CSS


def test_hover_and_focus_remain() -> None:
    assert ".mention:hover {" in REFERENCE_CSS
    # The pill is a link: it keeps the app's global visible focus ring.
    assert ":focus-visible" in MAIN_CSS
    assert "outline: 3px solid var(--cobalt)" in MAIN_CSS


def test_prose_link_rules_still_yield_to_the_reference() -> None:
    assert ".prose .mention," in REFERENCE_CSS
    assert 'html[data-accent="gradiente"] .prose a.mention' in REFERENCE_CSS


def test_mention_menu_is_skinned() -> None:
    assert ".cm-tooltip.cm-tooltip-autocomplete" in REFERENCE_CSS
    assert ".cm-completionLabel" in REFERENCE_CSS
    assert ".cm-completionDetail" in REFERENCE_CSS
    # The tint of each suggestion becomes a colored dot.
    assert ".cm-completionIcon-p1" in REFERENCE_CSS
    assert ".cm-completionIcon-p12" in REFERENCE_CSS
