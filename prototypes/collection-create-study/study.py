"""Typed fixture and raw-page renderer for the collection creation study.

The page is the real ``pages.characters.CharacterList`` rendered by the
application catalog. The study adds one comparison strip, one stylesheet and
one script; it does not replace the page shell or its assets. Both entry
options read the same DOM, the same cards and the same creation button.

The card names come from the approved demonstration set in
``prototypes/devin-prototype/personaggi.html`` and the reference draft in
``seed/boschetto-di-smeraldo.yaml``. A collection long enough to test the
retained card repeats those names with a numeral and adds one long stress name;
both are labelled demonstration scaffolding, not campaign content.
"""

import json
import subprocess
import uuid
from pathlib import Path

from pydantic import BaseModel

from backend.jinja import get_catalog
from backend.navigation import CardItem, Crumb, PageLink, WorldContext, world_nav

HERE = Path(__file__).parent
REPO = HERE.parents[1]
COMPONENTS = REPO / "src" / "frontend" / "components"
WORLD_ID = "4d2f0b7a-1c3e-4a55-9b2f-8e6a1d0c7f31"
WORLD_NAME = "Il Boschetto di Smeraldo"

# name, title, tint, animal, player — the approved demonstration cast.
CAST = (
    ("Rugginosa", "La Senza Tana", "p1", "🐈", "Giulia"),
    ("Barone Talpa", "Duca di Roccianera", "p8", "🦫", "Marco"),
    ("Foglia di Ferro", "Custode del Bosco Antico", "p5", "🦌", "Sara"),
    ("Corvinus", "Primo Complottista", "p10", "🐦‍⬛", "Luca"),
    ("Mastro Tasso", "Socio della Compagnia del Fiume", "p3", "🦡", "Giulia"),
    ("Sibilla", "Voce del Culto", "p6", "🦎", "Marco"),
)
LONG_NAME = "Rugginosa la Custode delle Mappe Rubate del Guado Spezzato"
NUMERALS = ("", "II", "III", "IV", "V")
DRAFT_NAME = "Lo Scoiattolo Smemorato"
DRAFT_ANIMAL = "🐿️"
DRAFT_TINT = "p11"
# collection key, published entries, draft entries.
SIZES = (("empty", 0, 0), ("short", 3, 2), ("long", 30, 3))

# The numbers the comparison is decided on. Capture writes them and the focused
# test asserts them, so both read the same definition: the document offset of
# the first real card, the scroll needed to reveal the creation entry and its
# hint, the tap-target box, the actions above the collection, and overflow.
MEASURE_JS = """() => {
  const visible = (element) => {
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return style.display !== "none" && style.visibility !== "hidden"
      && rect.width > 0 && rect.height > 0;
  };
  const create = document.querySelector('[data-testid="create-character"]');
  const published = document.querySelector('.container > .grid');
  const first = published
    ? published.querySelector(':scope > .entity-card')
    : null;
  const hint = create
    ? create.querySelector('.collection-create__hint')
    : null;
  const createBox = create ? create.getBoundingClientRect() : null;
  const firstBox = first ? first.getBoundingClientRect() : null;
  const hintBox = hint ? hint.getBoundingClientRect() : null;
  const createTop = createBox ? createBox.top + scrollY : null;
  const firstTop = firstBox ? firstBox.top + scrollY : null;
  const header = [...document.querySelectorAll(
    '.topbar a[href], .topbar button, .masthead a[href], .masthead button'
  )].filter(visible);
  const createAboveFirst = createBox
    ? (firstBox ? createBox.bottom <= firstBox.top : true)
    : null;
  return {
    first_card_top: firstTop,
    first_card_reveal: firstBox
      ? Math.max(0, firstTop + firstBox.height - innerHeight)
      : null,
    create_top: createTop,
    create_reveal: createBox
      ? Math.max(0, createTop + createBox.height - innerHeight)
      : null,
    create_width: createBox ? createBox.width : null,
    create_height: createBox ? createBox.height : null,
    create_parent: create ? create.parentElement.className : null,
    create_above_first_card: createAboveFirst,
    hint_reveal: hintBox
      ? Math.max(0, hintBox.top + scrollY + hintBox.height - innerHeight)
      : null,
    header_actions: header.length,
    top_actions: header.length + (createAboveFirst ? 1 : 0),
    cards: published
      ? published.querySelectorAll(':scope > .entity-card').length
      : 0,
    drafts: document.querySelectorAll('.section .entity-card').length,
    document_height: document.documentElement.scrollHeight,
    horizontal_overflow: document.documentElement.scrollWidth > innerWidth,
  };
}"""


class StudyCollection(BaseModel):
    """One collection state: the published cards and the drafts below them."""

    key: str
    published: list[CardItem]
    drafts: list[CardItem]


class StudyWorld(BaseModel):
    id: str
    name: str


class StudyUser(BaseModel):
    name: str
    email: str
    role: str
    avatar_url: str | None = None
    symbol_style: str = "icons"


def _href(key: str, index: int) -> str:
    identifier = uuid.uuid5(
        uuid.NAMESPACE_URL, f"collection-create-study/{key}/{index}"
    )
    return f"/worlds/{WORLD_ID}/characters/{identifier}"


def _published(count: int, key: str) -> list[CardItem]:
    cards = []
    for index in range(count):
        name, title, tint, animal, player = CAST[index % len(CAST)]
        cycle = index // len(CAST)
        if index == 0:
            name = LONG_NAME
        elif cycle:
            name = f"{name} {NUMERALS[cycle]}"
        cards.append(
            CardItem(
                name=name,
                href=_href(key, index),
                tint=tint,
                animal=animal,
                title=title,
                owner_label=f"Giocato da {player}",
            )
        )
    return cards


def _drafts(count: int, key: str) -> list[CardItem]:
    return [
        CardItem(
            name=DRAFT_NAME if index == 0 else f"{DRAFT_NAME} {NUMERALS[index]}",
            href=_href(f"{key}-draft", index),
            tint=DRAFT_TINT,
            animal=DRAFT_ANIMAL,
            owner_label="Giocato da Ada",
        )
        for index in range(count)
    ]


def collection(key: str) -> StudyCollection:
    published, drafts = next(
        (published, drafts) for size, published, drafts in SIZES if size == key
    )
    return StudyCollection(
        key=key,
        published=_published(published, key),
        drafts=_drafts(drafts, key),
    )


def props(key: str) -> dict:
    state = collection(key)
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
        "cards": state.published,
        "drafts": state.drafts,
        "crumbs": [
            Crumb(label="Mondi", href="/worlds"),
            Crumb(label=WORLD_NAME, href=f"/worlds/{WORLD_ID}"),
            Crumb(label="Personaggi"),
        ],
        "current_user": StudyUser(name="Ada", email="ada@example.com", role="admin"),
    }


def _inject(html: str, key: str) -> str:
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
        "<body ", f'<body data-study-entry="a" data-study-size="{key}" ', 1
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


def render_page(key: str) -> str:
    """Render one collection state and return the raw full page."""
    catalog = get_catalog(
        str(COMPONENTS), env="dev", app_name="collection-create-study"
    )
    page = catalog.render("pages.characters.CharacterList", **props(key))
    return _inject(str(page), key)


def revisions() -> dict:
    """The source revision the captures describe."""
    base = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    files = (
        "src/frontend/components/pages/characters/CharacterList.jinja",
        "src/frontend/components/editorial/EntityCard.jinja",
        "src/frontend/components/editorial/EntityCard.css",
        "src/frontend/components/editorial/CollectionCreate.jinja",
        "src/frontend/components/editorial/CollectionCreate.css",
        "src/frontend/components/editorial/Collection.css",
        "src/frontend/components/common/Grid.jinja",
        "src/frontend/components/common/Grid.css",
        "src/frontend/components/editorial/Masthead.jinja",
        "src/frontend/components/editorial/Masthead.css",
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
            "sizes": {
                size: {"published": published, "drafts": drafts}
                for size, published, drafts in SIZES
            },
            "long_name": LONG_NAME,
            "draft_name": DRAFT_NAME,
        },
    }


if __name__ == "__main__":
    print(json.dumps(revisions(), indent=2))
