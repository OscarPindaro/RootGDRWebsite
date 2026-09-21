"""The autosave status is a single page-level indicator.

Identity, summary, body and metadata share one document: each used to render
its own ``[data-autosave-status]``, so the same "Salvato" appeared several
times. Only ``layout.Page`` owns the indicator now.
"""

from pathlib import Path
from types import SimpleNamespace

from backend.jinja import get_catalog

COMPONENTS_DIR = Path(__file__).parents[3] / "src" / "frontend" / "components"


def _catalog():
    return get_catalog(str(COMPONENTS_DIR), app_name="Root GDR")


def test_document_blocks_do_not_render_their_own_status() -> None:
    catalog = _catalog()
    common = {
        "base": "/worlds/w",
        "version": 1,
        "can_manage": True,
    }
    blocks = [
        catalog.render("editorial.DocIdentity", **common, content="<h1>x</h1>"),
        catalog.render(
            "editorial.DocEdit",
            world_id="w",
            body="",
            body_html="",
            **common,
        ),
        catalog.render(
            "editorial.DocSummary",
            world_id="w",
            value="",
            value_html="",
            **common,
        ),
        catalog.render("editorial.Metadata", fields=[], **common),
    ]

    for html in blocks:
        assert "data-autosave-status" not in str(html)


def test_page_owns_exactly_one_status_indicator() -> None:
    user = SimpleNamespace(
        name="Ada",
        email="ada@example.com",
        role="member",
        avatar_url=None,
        symbol_style="icons",
    )
    html = str(
        _catalog().render(
            "layout.Page", title="Prova", current_user=user, content="<p>ciao</p>"
        )
    )

    assert html.count("data-autosave-status") == 1
