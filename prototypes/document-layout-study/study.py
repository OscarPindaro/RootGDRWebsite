"""Typed fixture and raw-page renderer for the document layout study.

The page is the real ``pages.characters.CharacterDetail`` rendered by the
application catalog. The study adds one comparison strip, one layout
stylesheet and one script; it does not replace the document shell or its
assets. Both arrangements read the same DOM and the same fixture data.
"""

import json
import subprocess
from pathlib import Path

from pydantic import BaseModel

from backend.content.constants import ContentKind
from backend.content.markdown import MentionTarget, render_markdown
from backend.content.references import Backlink
from backend.content.view_helpers import animal_options, tint_options
from backend.jinja import get_catalog
from backend.navigation import Crumb, PageLink, WorldContext, world_nav

HERE = Path(__file__).parent
REPO = HERE.parents[1]
COMPONENTS = REPO / "src" / "frontend" / "components"
WORLD_ID = "4d2f0b7a-1c3e-4a55-9b2f-8e6a1d0c7f31"
CHARACTER_ID = "9a1c5e2d-7b4f-4c08-a3d6-2f9e8b0c1a54"
WORLD_NAME = "Il Boschetto di Smeraldo"
CHARACTER_NAME = "Rugginosa"
BODY = """Rugginosa non ricorda il proprio nome di cucciola. Ricorda il fumo, il rumore delle assi che cedono e la sensazione di essere l'unica cosa che in quella radura non aveva una casa. Da allora si è fatta un mestiere dell'assenza di casa: cammina, osserva, vende ciò che vede.

## Come è arrivata a Muschioverde

Nella primavera del terzo anno attraversò il @[Il Guado Spezzato] con un carico di mappe rubate a un corriere della Marchesa. Non cercava protezione: cercava un posto dove le mappe valessero qualcosa. A @[Muschioverde] scoprì che nessuno sapeva leggerle meglio di lei.

> «Non servo nessuno. Vendo informazioni e, se il prezzo è buono, dimentico di averle vendute.»

## Rapporti

- @[Barone Talpa] — le deve due favori e una barca.
- @[Foglia di Ferro] — l'unica che le ha offerto una casa; l'unica che ha rifiutato.
- @[Corvinus] — socio occasionale, mai alleato.

## Evoluzione in campagna

Dalla prima sessione a oggi ha cambiato padrone tre volte senza mai cambiare idea su di sé. Il suo arco riguarda la differenza fra non avere una casa e non volerne una.

Torna spesso alla @[Radura della Grande Quercia], dove ha una cassa sepolta che nessuno ha ancora trovato."""
SHORT = "Una gatta randagia che ha imparato a leggere le mappe prima delle persone."


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


def _mentions() -> dict[str, MentionTarget]:
    targets = (
        ("Il Guado Spezzato", ContentKind.PLACE, "p6", "place-guado", "places"),
        ("Muschioverde", ContentKind.PLACE, "p5", "place-muschioverde", "places"),
        ("Barone Talpa", ContentKind.NPC, "p2", "npc-barone", "npcs"),
        ("Foglia di Ferro", ContentKind.NPC, "p4", "npc-foglia", "npcs"),
        ("Corvinus", ContentKind.NPC, "p10", "npc-corvinus", "npcs"),
        (
            "Radura della Grande Quercia",
            ContentKind.PLACE,
            "p3",
            "place-radura",
            "places",
        ),
    )
    return {
        name: MentionTarget(
            id=slug,
            kind=kind,
            tint=tint,
            href=f"/worlds/{WORLD_ID}/{section}/{slug}",
            name=name,
        )
        for name, kind, tint, slug, section in targets
    }


def _links() -> dict[ContentKind, list[Backlink]]:
    return {
        ContentKind.SESSION: [
            Backlink(
                kind=ContentKind.SESSION,
                name="Il pedaggio del Guado",
                href=f"/worlds/{WORLD_ID}/sessions/5b7c1d90-2e4a-4f18-8c63-7a9d0e2b4f11",
                tint="p5",
            )
        ],
        ContentKind.STORY: [
            Backlink(
                kind=ContentKind.STORY,
                name="L'inverno dei corvi",
                href=f"/worlds/{WORLD_ID}/stories/1f4e8a2c-9d70-4b36-a5e1-0c8b7d3f6a22",
                tint="p8",
            )
        ],
        ContentKind.PLACE: [
            Backlink(
                kind=ContentKind.PLACE,
                name="Radura della Grande Quercia",
                href=f"/worlds/{WORLD_ID}/places/place-radura",
                tint="p3",
            )
        ],
    }


def props() -> dict:
    character = StudyCharacter(
        id=CHARACTER_ID,
        name=CHARACTER_NAME,
        title="La Senza Tana",
        short_description=SHORT,
        body=BODY,
        tint="p1",
        animal="🐈",
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
        "body_html": render_markdown(BODY, _mentions()),
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
    html = html.replace("<body ", '<body data-study-layout="a" ', 1)
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
    catalog = get_catalog(str(COMPONENTS), env="dev", app_name="document-layout-study")
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
        "src/frontend/components/editorial/DocIdentity.jinja",
        "src/frontend/components/editorial/DocEdit.jinja",
        "src/frontend/components/editorial/DocSummary.jinja",
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
