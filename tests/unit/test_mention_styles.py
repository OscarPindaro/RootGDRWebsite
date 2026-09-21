"""The "@" menu and the in-editor mention use the app skin, not the defaults.

The menu is CodeMirror's autocomplete (``.cm-tooltip-autocomplete``) and the
mention while writing is ``.cm-lp-mention``. Neither can be exercised without a
browser, so this guards the wiring: the styles exist and the kind travels from
the mention text to the decoration.
"""

from pathlib import Path

ROOT = Path(__file__).parents[2]
MAIN_CSS = (ROOT / "src/frontend/static/css/main.css").read_text()
LIVE_PREVIEW = (ROOT / "src/frontend/js/editor/live-preview.js").read_text()


def test_mention_menu_is_skinned() -> None:
    assert ".cm-tooltip.cm-tooltip-autocomplete" in MAIN_CSS
    assert ".cm-completionLabel" in MAIN_CSS
    assert ".cm-completionDetail" in MAIN_CSS
    # The tint of each suggestion becomes a colored dot.
    assert ".cm-completionIcon-p1" in MAIN_CSS
    assert ".cm-completionIcon-p12" in MAIN_CSS


def test_edit_mention_reuses_the_rendered_pill() -> None:
    assert ".cm-lp-mention[data-kind]" in MAIN_CSS
    for kind in ("personaggio", "npc", "luogo", "sessione", "storia", "pagina"):
        assert f'.cm-lp-mention[data-kind="{kind}"]' in MAIN_CSS
    # The editor tags the mention with its kind so the pill can show the icon.
    assert 'attributes: { "data-kind": kind }' in LIVE_PREVIEW
    assert '"data-kind"' in LIVE_PREVIEW
