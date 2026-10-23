"""Typed fixture and raw-page renderer for the phone appearance study.

The page is the real ``pages.characters.CharacterDetail`` rendered by the
application catalog. The study adds one comparison strip, one stylesheet and
one script; it does not replace the document shell or its assets. Both
arrangements read the same DOM and the same fixture data.
"""

import json
import subprocess
from pathlib import Path

from pydantic import BaseModel

from backend.content.constants import ContentKind
from backend.content.markdown import render_markdown
from backend.content.references import Backlink
from backend.content.view_helpers import animal_options, tint_options
from backend.jinja import get_catalog
from backend.navigation import Crumb, PageLink, WorldContext, world_nav

HERE = Path(__file__).parent
REPO = HERE.parents[1]
COMPONENTS = REPO / "src" / "frontend" / "components"
WORLD_ID = "7c1e4a90-3b6d-4f21-8a5e-9d2c6b0f4e13"
CHARACTER_ID = "2f8b6d1c-5a3e-4c79-b0d4-6e9a1f7c3b52"
WORLD_NAME = "Il Boschetto di Smeraldo"
CHARACTER_NAME = "Fiamma Rossa"
SHORT = "Vende tutto, comprese le informazioni."
BODY = (
    "Porta sale al Cerchio di Pietre. Conosce i sentieri del bosco e commercia "
    "con tutte le fazioni."
)


class StudyOwner(BaseModel):
    name: str


class StudyCharacter(BaseModel):
    id: str
    name: str
    title: str
    short_description: str
    body: str
    tint: str
    animal: str
    image_url: str | None = None
    locked: bool = False
    is_draft: bool = False
    version: int = 1
    owner: StudyOwner


class StudyWorld(BaseModel):
    id: str
    name: str


class StudyUser(BaseModel):
    name: str
    email: str
    role: str
    avatar_url: str | None = None
    symbol_style: str = "icons"


def _links() -> dict[ContentKind, list[Backlink]]:
    return {
        ContentKind.PLACE: [
            Backlink(
                kind=ContentKind.PLACE,
                name="Il Guado",
                href=f"/worlds/{WORLD_ID}/places/place-guado",
                tint="p1",
            )
        ],
    }


def props() -> dict:
    character = StudyCharacter(
        id=CHARACTER_ID,
        name=CHARACTER_NAME,
        title="Mercante del Guado",
        short_description=SHORT,
        body=BODY,
        tint="p8",
        animal="🦊",
        owner=StudyOwner(name="Ada"),
    )
    return {
        "world": StudyWorld(id=WORLD_ID, name=WORLD_NAME),
        "world_context": WorldContext(id=WORLD_ID, name=WORLD_NAME, role="Master"),
        "nav": world_nav(WORLD_ID, "personaggi"),
        "pages": [
            PageLink(
                label="Le regole della Casa",
                href=f"/worlds/{WORLD_ID}/pages/le-regole-della-casa",
            )
        ],
        "character": character,
        "animals": animal_options(),
        "tints": tint_options(),
        "short_html": render_markdown(SHORT),
        "body_html": render_markdown(BODY),
        "links": _links(),
        "can_manage": True,
        "auto_edit": False,
        "crumbs": [
            Crumb(label="Mondi", href="/worlds"),
            Crumb(label=WORLD_NAME, href=f"/worlds/{WORLD_ID}"),
            Crumb(label=CHARACTER_NAME),
        ],
        "current_user": StudyUser(name="Ada", email="ada@example.com", role="admin"),
    }


def _inject(html: str) -> str:
    """Add the study strip, stylesheet and script to the real page document."""
    style = (HERE / "comparison.css").read_text()
    script = (HERE / "comparison.js").read_text()
    controls = (HERE / "controls.html").read_text()
    assert (
        html.count("<body ") == 1
        and html.count("</head>") == 1
        and html.count("</body>") == 1
    )
    html = html.replace(
        "</head>", f"<style data-study-style>\n{style}\n</style>\n</head>", 1
    )
    html = html.replace(
        "<body ",
        '<body data-study-appearance="always" data-study-expanded="false" ',
        1,
    )
    body_start = html.index("<body ")
    body_end = html.index(">", body_start) + 1
    html = html[:body_end] + f"\n{controls}" + html[body_end:]
    html = html.replace(
        "</body>",
        f"<script data-study-script>\n{script}\n</script>\n</body>",
        1,
    )
    return html


def render_page() -> str:
    """Render the real character document and return the raw full page."""
    catalog = get_catalog(str(COMPONENTS), env="dev", app_name="appearance-study")
    return _inject(str(catalog.render("pages.characters.CharacterDetail", **props())))


def revisions() -> dict:
    """The source revision the captures describe."""
    base = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    files = (
        "src/frontend/components/pages/characters/CharacterDetail.jinja",
        "src/frontend/components/editorial/Document.css",
        "src/frontend/components/editorial/ImageEditor.jinja",
        "src/frontend/components/editorial/ImageEditor.css",
        "src/frontend/components/editorial/ImageEditor.js",
        "src/frontend/components/editorial/DocIdentity.jinja",
        "src/frontend/components/editorial/DocEdit.jinja",
        "src/frontend/components/editorial/DocSummary.jinja",
        "src/frontend/components/common/ChoiceGrid.css",
        "src/frontend/components/common/Button.css",
        "prototypes/appearance-study/comparison.css",
        "prototypes/appearance-study/comparison.js",
        "prototypes/appearance-study/study.py",
    )
    blobs = subprocess.run(
        ["git", "-C", str(REPO), "hash-object", *files],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()
    return {
        "base_commit": base,
        "component_blobs": dict(zip(files, blobs, strict=True)),
        "fixture": {
            "world_id": WORLD_ID,
            "character_id": CHARACTER_ID,
            "name": CHARACTER_NAME,
        },
    }


if __name__ == "__main__":
    print(json.dumps(revisions(), indent=2))
