"""Navigation view-models built on the server.

The rail is server-rendered, so the active item, the marks and the counts are
decided here rather than in the browser. Values are typed models, not dicts.
"""

from typing import Literal

from pydantic import BaseModel, Field


class NavItem(BaseModel):
    id: str
    label: str
    href: str
    mark: str
    count: int | None = None
    style: str | None = None


class PageLink(BaseModel):
    label: str
    href: str


class WorldContext(BaseModel):
    """The world identity shown at the top of the rail."""

    id: str
    name: str
    role: str


class Crumb(BaseModel):
    """One step in a breadcrumb trail."""

    label: str
    href: str | None = None


class TimelineEntry(BaseModel):
    """One event in a timeline (diary, activity)."""

    when: str
    title: str
    href: str
    text: str = ""
    tint: str | None = None


class QuickEntry(BaseModel):
    """An entry point to a content section on the world overview."""

    label: str
    href: str
    mark: str
    foot: str
    count: int
    accent: str


class CardItem(BaseModel):
    """A content item rendered as a card (character, NPC, place)."""

    name: str
    href: str
    tint: str
    title: str | None = None
    animal: str | None = None
    shape: str | None = None
    image_url: str | None = None
    owner_label: str | None = None
    tag: str | None = None


class Option(BaseModel):
    """A labelled option for a select control."""

    value: str
    label: str


class ButtonGroupOption(Option):
    icon: str | None = None
    aria_label: str | None = None
    disabled: bool = False


class MetadataField(BaseModel):
    """A typed field rendered and autosaved by the document metadata editor."""

    name: str
    label: str
    kind: Literal["text", "date", "number", "select", "multiselect"]
    value: str | int | None = None
    values: list[str] = Field(default_factory=list)
    options: list[Option] = Field(default_factory=list)


def global_nav(active: str | None, is_admin: bool, env: str) -> list[NavItem]:
    """Navigation shown outside a world."""
    items = [
        NavItem(id="home", label="Home", href="/", mark="mondo"),
        NavItem(id="worlds", label="Mondi", href="/worlds", mark="mondi"),
    ]
    if is_admin:
        items.append(
            NavItem(
                id="admin-users", label="Utenti", href="/admin/users", mark="profilo"
            )
        )
        if env == "dev":
            items.append(
                NavItem(
                    id="showcase", label="Componenti", href="/components", mark="pagina"
                )
            )
    return items


# section id (used for the active state and counts), label, mark, URL path.
# The path is always English while the section id stays Italian; the two are
# separate so deriving an href from the id cannot produce a 404.
WORLD_SECTIONS: tuple[tuple[str, str, str, str | None], ...] = (
    ("mondo", "Panoramica", "mondo", None),
    ("personaggi", "Personaggi", "personaggi", "characters"),
    ("npc", "NPC", "npc", "npcs"),
    ("luoghi", "Luoghi", "luoghi", "places"),
    ("sessioni", "Sessioni", "sessioni", "sessions"),
    ("storie", "Storie", "storie", "stories"),
    ("pagine", "Pagine", "pagine", "pages"),
)


def world_nav(
    world_id: str,
    active: str | None,
    counts: dict[str, int] | None = None,
) -> list[NavItem]:
    """Navigation shown inside a world, with per-section counts when known."""
    counts = counts or {}
    items = []
    for section_id, label, mark, path in WORLD_SECTIONS:
        href = f"/worlds/{world_id}" if path is None else f"/worlds/{world_id}/{path}"
        items.append(
            NavItem(
                id=section_id,
                label=label,
                href=href,
                mark=mark,
                count=counts.get(section_id),
            )
        )
    return items


# section id, label, mark, sub-label, accent, URL path
QUICK_SECTIONS: tuple[tuple[str, str, str, str, str, str], ...] = (
    ("personaggi", "Personaggi", "personaggi", "Schede", "vermilion", "characters"),
    ("npc", "NPC", "npc", "Solo Master", "plum", "npcs"),
    ("luoghi", "Luoghi", "luoghi", "Atlante", "forest", "places"),
    ("sessioni", "Sessioni", "sessioni", "Registro", "cobalt", "sessions"),
    ("storie", "Storie", "storie", "Archi", "ochre", "stories"),
)


def build_quicks(
    world_id: str, counts: dict[str, int] | None = None
) -> list[QuickEntry]:
    """The strip of entry points to the content sections on the overview."""
    counts = counts or {}
    return [
        QuickEntry(
            label=label,
            href=f"/worlds/{world_id}/{path}",
            mark=mark,
            foot=foot,
            count=counts.get(section_id, 0),
            accent=accent,
        )
        for section_id, label, mark, foot, accent, path in QUICK_SECTIONS
    ]
