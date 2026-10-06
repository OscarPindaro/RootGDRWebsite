"""The ``@`` menu's marks (REQ-0009/T02).

The suggestion menu replaces CodeMirror's tint dot with a fixed rectangular
mark: the stored animal for characters and NPCs, the stored shape for places,
and the kind cue as the fallback. Names and tokens are written as text and
attributes — never as HTML — long names ellipsize instead of stretching the
menu, and Up/Down/Enter keep inserting the mention.
"""

import pytest

from backend.content.markdown import render_markdown

pytestmark = pytest.mark.frontend

MENTIONS = "/api/worlds/w/mentions"

SUGGESTIONS = [
    {
        "name": "Fiamma Rossa",
        "kind": "personaggio",
        "tint": "p1",
        "insert": "Fiamma Rossa",
        "animal": "🐈",
        "shape": None,
    },
    {
        "name": "Radura",
        "kind": "luogo",
        "tint": "p5",
        "insert": "Radura",
        "animal": None,
        "shape": "rombo",
    },
    {
        "name": "Il risveglio",
        "kind": "storia",
        "tint": "p3",
        "insert": "storia:Il risveglio",
        "animal": None,
        "shape": None,
    },
    {
        "name": "Un nome davvero molto lungo che non deve allargare il menu",
        "kind": "sessione",
        "tint": "p2",
        "insert": "sessione:Un nome davvero molto lungo che non deve allargare il menu",
        "animal": None,
        "shape": None,
    },
    {
        "name": "<script>alert(1)</script>",
        "kind": "pagina",
        "tint": "p4",
        "insert": "pagina:<script>alert(1)</script>",
        "animal": None,
        "shape": None,
    },
]


def _open_menu(component) -> None:
    component.route_json("GET", MENTIONS, body={"data": SUGGESTIONS})
    page = component.mount(
        "editorial.DocEdit",
        props={
            "world_id": "w",
            "base": "/worlds/w/characters/1",
            "body": "Testo esistente.",
            "body_html": render_markdown("Testo esistente.", {}),
            "version": "1",
            "can_manage": True,
        },
    )
    page.add_script_tag(url="/static/js/editor.js")
    page.wait_for_selector("[data-doc-render]")
    page.dblclick("[data-doc-render]")
    page.wait_for_selector(".cm-editor")
    page.locator(".cm-content").click()
    page.keyboard.type("@")
    page.wait_for_selector('.cm-tooltip-autocomplete li[aria-selected="true"]')
    return page


def _marks(page) -> list[dict]:
    return page.evaluate(
        """() => [...document.querySelectorAll('.cm-tooltip-autocomplete li')]
            .map((item) => {
                const mark = item.querySelector('.mention-mark');
                const box = mark.getBoundingClientRect();
                const label = item.querySelector('.cm-completionLabel');
                return {
                    mark: mark ? {
                        text: mark.textContent,
                        shape: mark.dataset.shape || null,
                        kind: mark.dataset.kind || null,
                        tint: mark.dataset.tint || null,
                        animal: mark.classList.contains('mention-mark--animal'),
                        width: box.width, height: box.height,
                    } : null,
                    label: label ? label.textContent : null,
                    detail: item.querySelector('.cm-completionDetail')?.textContent,
                };
            })"""
    )


def test_the_menu_marks_animals_shapes_and_kind_cues(component):
    page = _open_menu(component)

    marks = {row["label"]: row for row in _marks(page)}
    animal = marks["Fiamma Rossa"]["mark"]
    assert animal["animal"] is True
    assert animal["text"] == "🐈"
    shape = marks["Radura"]["mark"]
    assert shape["shape"] == "rombo"
    assert shape["text"] == ""
    story = marks["Il risveglio"]["mark"]
    assert story["kind"] == "storia"
    # The kind detail keeps its Italian word.
    assert marks["Il risveglio"]["detail"] == "storia"


def test_the_mark_keeps_its_size_and_long_names_ellipsize(component):
    page = _open_menu(component)

    marks = _marks(page)
    sizes = {(row["mark"]["width"], row["mark"]["height"]) for row in marks}
    assert len(sizes) == 1

    overflow = page.evaluate(
        """() => {
            const label = [...document.querySelectorAll('.cm-completionLabel')]
                .find((node) => node.textContent.startsWith('Un nome davvero'));
            const style = getComputedStyle(label);
            return {clipped: label.scrollWidth > label.clientWidth,
                    overflow: style.textOverflow, whiteSpace: style.whiteSpace};
        }"""
    )
    assert overflow["clipped"] is True
    assert overflow["overflow"] == "ellipsis"
    assert overflow["whiteSpace"] == "nowrap"


def test_a_hostile_name_stays_text(component):
    page = _open_menu(component)

    injected = page.evaluate(
        """() => {
            const label = [...document.querySelectorAll('.cm-completionLabel')]
                .find((node) => node.textContent.includes('script'));
            return {
                text: label?.textContent,
                elements: document.querySelectorAll(
                    '.cm-tooltip-autocomplete script'
                ).length,
            };
        }"""
    )
    assert injected["text"] == "<script>alert(1)</script>"
    assert injected["elements"] == 0


def test_selection_inserts_the_mention(component):
    page = _open_menu(component)

    def content() -> str:
        return page.evaluate("() => document.querySelector('.cm-content').textContent")

    # The first entry is active; Enter applies it, the arrows move on.
    page.keyboard.press("Enter")
    assert "@[Fiamma Rossa]" in content()

    page.keyboard.type("@")
    page.wait_for_selector('.cm-tooltip-autocomplete li[aria-selected="true"]')
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    assert "@[Radura]" in content()
