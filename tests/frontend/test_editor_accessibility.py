"""The open CodeMirror textbox carries the visible field label.

CodeMirror builds its own ``.cm-content[role="textbox"]``; the hidden source
textarea and the rendered block labels do not name it. Each mount path — the
legacy Markdown form field, the document body and the compact summary — must
derive the content textbox's accessible name from the label the reader already
sees, so axe's ``aria-input-field-name`` rule stays clean while the editor is
open (REQ-0019/T33).
"""

from pathlib import Path

import pytest
from playwright.sync_api import expect

from backend.content.markdown import render_markdown

pytestmark = pytest.mark.frontend

AXE = Path(__file__).parents[2] / "node_modules" / "axe-core" / "axe.min.js"
AUTOSAVE = "/api/worlds/w/characters/1"


def _unnamed_textboxes(page) -> list[str]:
    page.add_script_tag(content=AXE.read_text(encoding="utf-8"))
    return page.evaluate(
        """async () => {
            const results = await axe.run(document, {
                runOnly: {type: 'rule', values: ['aria-input-field-name']},
                resultTypes: ['violations'],
            });
            return results.violations.flatMap(
                (violation) => violation.nodes.map((node) => node.target.join(' '))
            );
        }"""
    )


def _mount_body(component, **overrides) -> object:
    component.route_json("PATCH", AUTOSAVE, body={"version": 2})
    props = {
        "world_id": "w",
        "base": "/worlds/w/characters/1",
        "body": "Corpo iniziale.",
        "body_html": render_markdown("Corpo iniziale.", {}),
        "version": "1",
        "can_manage": True,
    }
    props.update(overrides)
    page = component.mount("editorial.DocEdit", props=props)
    page.add_script_tag(url="/static/js/editor.js")
    page.wait_for_selector("[data-doc-render]", state="attached")
    page.dblclick("[data-doc-render]")
    page.wait_for_selector("[data-doc-edit] .cm-editor")
    return page


def _mount_summary(component) -> object:
    component.route_json("PATCH", AUTOSAVE, body={"version": 2})
    page = component.mount(
        "editorial.DocSummary",
        props={
            "world_id": "w",
            "base": "/worlds/w/characters/1",
            "value": "Sintesi iniziale.",
            "value_html": render_markdown("Sintesi iniziale.", {}),
            "version": "1",
            "can_manage": True,
        },
    )
    page.add_script_tag(url="/static/js/editor.js")
    page.wait_for_selector("[data-summary-render]", state="attached")
    page.dblclick("[data-summary-render]")
    page.wait_for_selector("[data-doc-summary] .cm-editor")
    return page


def _mount_markdown_field(component) -> object:
    page = component.mount(
        "common.Field",
        props={
            "label": "Descrizione",
            "name": "description",
            "type": "textarea",
            "value": "Testo iniziale.",
        },
    )
    page.evaluate(
        """() => {
            const field = document.querySelector('.field');
            field.dataset.mdTabs = '';
            field.querySelector('textarea').dataset.markdownField = '';
        }"""
    )
    page.add_script_tag(url="/static/js/editor.js")
    page.wait_for_selector(".cm-editor")
    return page


def test_the_document_body_textbox_is_named_after_its_field(component):
    page = _mount_body(component)

    editor = page.locator("[data-doc-edit] .cm-content")
    expect(editor).to_have_accessible_name("Testo Markdown")
    assert _unnamed_textboxes(page) == []


def test_the_world_description_textbox_reuses_its_accepted_label(component):
    page = _mount_body(
        component, field_name="description", label="Descrizione del mondo"
    )

    editor = page.locator('[data-doc-field-name="description"] .cm-content')
    expect(editor).to_have_accessible_name("Descrizione del mondo")
    assert _unnamed_textboxes(page) == []


def test_the_summary_textbox_is_named_after_its_visible_label(component):
    page = _mount_summary(component)

    editor = page.locator("[data-doc-summary] .cm-content")
    expect(editor).to_have_accessible_name("Sintesi")
    assert _unnamed_textboxes(page) == []


def test_the_legacy_markdown_field_textbox_is_named_by_its_label(component):
    page = _mount_markdown_field(component)

    editor = page.locator(".cm-content")
    expect(editor).to_have_accessible_name("Descrizione")
    assert _unnamed_textboxes(page) == []


def test_the_three_mounts_keep_distinct_names(component):
    names = []

    body = _mount_body(component)
    names.append(
        body.locator("[data-doc-edit] .cm-content").get_attribute("aria-label")
    )

    summary = _mount_summary(component)
    names.append(
        summary.locator("[data-doc-summary] .cm-content").get_attribute("aria-label")
    )

    description = _mount_body(
        component, field_name="description", label="Descrizione del mondo"
    )
    names.append(
        description.locator(
            '[data-doc-field-name="description"] .cm-content'
        ).get_attribute("aria-label")
    )

    assert names == ["Testo Markdown", "Sintesi", "Descrizione del mondo"]
