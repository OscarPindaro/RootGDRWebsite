"""Component tests for the reference (mention) weight.

A mention must read as a link inside a sentence, and it must look the same in
the two states the product shows it in: the server-rendered prose (``.mention``
in ``.docedit__render``) and the live-preview decoration while writing
(``.cm-lp-mention``). Both read the same ``--mention-*`` tokens, so this test
mounts the real ``editorial.DocEdit``, loads the real editor bundle, opens the
field and compares the two.

The editor renders its body at ``1rem`` while the reading page's ``.prose`` is
``1.16rem``; the geometry is em-based, so the absolute padding differs by that
ratio. The contract is that the *em* geometry, the corner and the weight are
identical — that is what "match in size, radius and weight" means here.
"""

import pytest

from backend.content.constants import ContentKind
from backend.content.markdown import MentionTarget, render_markdown

pytestmark = pytest.mark.frontend

TARGET = MentionTarget(
    id="1",
    kind=ContentKind.PLACE,
    tint="p5",
    href="/worlds/w/places/1",
    name="Radura della Grande Quercia",
)

# The mention sits on a line the selection is not on, so the live preview
# decorates it instead of showing the Markdown source. The label carries its
# kind so the pill shows the icon in both states.
LABEL = "luogo:Radura della Grande Quercia"
BODY = f"Fiamma Rossa vende sale.\n\nPorta tutto a @[{LABEL}].\n"


def _props() -> dict:
    return {
        "world_id": "w",
        "base": "/worlds/w/characters/1",
        "body": BODY,
        "body_html": render_markdown(BODY, {LABEL: TARGET}),
        "version": "1",
        "can_manage": True,
    }


def _style(page, selector: str) -> dict:
    return page.evaluate(
        """selector => {
            const el = document.querySelector(selector);
            if (!el) return null;
            const style = getComputedStyle(el);
            return {
                fontSize: parseFloat(style.fontSize),
                borderRadius: style.borderTopLeftRadius,
                fontWeight: style.fontWeight,
                paddingTop: parseFloat(style.paddingTop),
                paddingRight: parseFloat(style.paddingRight),
                paddingBottom: parseFloat(style.paddingBottom),
                paddingLeft: parseFloat(style.paddingLeft),
            };
        }""",
        selector,
    )


def _em(value: float, font_size: float) -> float:
    return round(value / font_size, 3)


def test_a_mention_reads_the_same_while_reading_and_while_writing(component):
    page = component.mount("editorial.DocEdit", props=_props())
    page.add_script_tag(url="/static/js/editor.js")
    page.wait_for_selector(".docedit__render .mention")

    rendered = _style(page, ".docedit__render .mention")
    assert rendered is not None

    page.dblclick("[data-doc-render]")
    page.wait_for_selector(".cm-lp-mention")
    edited = _style(page, ".cm-lp-mention")
    assert edited is not None

    # Weight and corner are absolute and must be identical.
    assert edited["fontWeight"] == rendered["fontWeight"] == "400"
    assert edited["borderRadius"] == rendered["borderRadius"] == "2px"

    # The padding is em-based; the two states must carry the same em geometry.
    for edge in ("paddingTop", "paddingRight", "paddingBottom", "paddingLeft"):
        assert _em(edited[edge], edited["fontSize"]) == _em(
            rendered[edge], rendered["fontSize"]
        ), f"{edge}: rendered {rendered} vs edited {edited}"


def test_the_mention_is_not_a_chip(component):
    page = component.mount("editorial.DocEdit", props=_props())
    page.wait_for_selector(".docedit__render .mention")

    style = page.evaluate(
        """() => {
            const el = document.querySelector('.docedit__render .mention');
            const style = getComputedStyle(el);
            return {
                radius: style.borderTopLeftRadius,
                weight: style.fontWeight,
                marginLeft: style.marginLeft,
                marginRight: style.marginRight,
                fontSize: parseFloat(style.fontSize),
                paddingInline: parseFloat(style.paddingLeft),
            };
        }"""
    )
    # A reduced corner and weight, no negative margin crowding the sentence,
    # and a padding that stays under half an em.
    assert style["radius"] == "2px"
    assert style["weight"] == "400"
    assert style["marginLeft"] == "0px"
    assert style["marginRight"] == "0px"
    assert style["paddingInline"] < 0.5 * style["fontSize"]


def test_the_kind_icon_survives_in_both_states(component):
    page = component.mount("editorial.DocEdit", props=_props())
    page.add_script_tag(url="/static/js/editor.js")
    page.wait_for_selector(".docedit__render .mention")

    rendered_icon = page.evaluate(
        """() => {
            const el = document.querySelector('.docedit__render .mention');
            const icon = getComputedStyle(el, '::before');
            return { width: icon.width, height: icon.height };
        }"""
    )
    assert rendered_icon["width"] not in ("", "0px")
    assert rendered_icon["height"] not in ("", "0px")

    page.dblclick("[data-doc-render]")
    page.wait_for_selector('.cm-lp-mention[data-kind="luogo"]')
    edited_icon = page.evaluate(
        """() => {
            const el = document.querySelector('.cm-lp-mention[data-kind="luogo"]');
            const icon = getComputedStyle(el, '::before');
            return { width: icon.width, height: icon.height };
        }"""
    )
    assert edited_icon["width"] not in ("", "0px")
    assert edited_icon["height"] not in ("", "0px")


def test_the_missing_reference_stays_a_helpful_placeholder(component):
    props = _props()
    props["body_html"] = render_markdown(BODY, {LABEL: None})
    page = component.mount("editorial.DocEdit", props=props)
    page.wait_for_selector(".docedit__render .mention--missing")

    style = page.evaluate(
        """() => {
            const el = document.querySelector('.docedit__render .mention--missing');
            const style = getComputedStyle(el);
            return {
                cursor: style.cursor,
                background: style.backgroundColor,
                icon: getComputedStyle(el, '::before').display,
            };
        }"""
    )
    assert style["cursor"] == "help"
    assert style["background"] in ("rgba(0, 0, 0, 0)", "transparent")
    assert style["icon"] == "none"


def test_the_mention_keeps_a_visible_focus_ring(component):
    page = component.mount("editorial.DocEdit", props=_props())
    page.wait_for_selector(".docedit__render .mention")

    # Reach the link by keyboard so the browser applies :focus-visible.
    for _ in range(6):
        if page.evaluate("() => document.activeElement?.classList.contains('mention')"):
            break
        page.keyboard.press("Tab")
    assert page.evaluate("() => document.activeElement?.classList.contains('mention')")
    outline = page.evaluate(
        "() => getComputedStyle(document.activeElement).outlineWidth"
    )
    assert outline not in ("", "0px")


# The stylesheet is the single owner of the reference root; the editor bundle
# only carries the decoration wiring. Guard the file that ships.
def test_the_reference_stylesheet_ships_with_the_document(component):
    page = component.mount("editorial.DocEdit", props=_props())
    links = page.evaluate(
        "() => [...document.styleSheets].map((sheet) => sheet.href || '')"
    )
    assert any(link.endswith("editorial/Reference.css") for link in links), links
