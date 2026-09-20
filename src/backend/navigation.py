"""Navigation view-models built on the server.

The rail is server-rendered, so the active item, the marks and the counts are
decided here rather than in the browser. Values are typed models, not dicts.
"""

from pydantic import BaseModel


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


WORLD_SECTIONS: tuple[tuple[str, str, str], ...] = (
    ("mondo", "Panoramica", "mondo"),
    ("personaggi", "Personaggi", "personaggi"),
    ("npc", "NPC", "npc"),
    ("luoghi", "Luoghi", "luoghi"),
    ("sessioni", "Sessioni", "sessioni"),
    ("storie", "Storie", "storie"),
    ("pagine", "Pagine", "pagine"),
)


def world_nav(
    world_id: str,
    active: str | None,
    counts: dict[str, int] | None = None,
) -> list[NavItem]:
    """Navigation shown inside a world, with per-section counts when known."""
    counts = counts or {}
    items = []
    for section_id, label, mark in WORLD_SECTIONS:
        href = (
            f"/worlds/{world_id}"
            if section_id == "mondo"
            else f"/worlds/{world_id}/{section_id}"
        )
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


# section id, label, mark, sub-label, accent
QUICK_SECTIONS: tuple[tuple[str, str, str, str, str], ...] = (
    ("personaggi", "Personaggi", "personaggi", "Schede", "vermilion"),
    ("npc", "NPC", "npc", "Solo Master", "plum"),
    ("luoghi", "Luoghi", "luoghi", "Atlante", "forest"),
    ("sessioni", "Sessioni", "sessioni", "Registro", "cobalt"),
    ("storie", "Storie", "storie", "Archi", "ochre"),
)


def build_quicks(
    world_id: str, counts: dict[str, int] | None = None
) -> list[QuickEntry]:
    """The strip of entry points to the content sections on the overview."""
    counts = counts or {}
    return [
        QuickEntry(
            label=label,
            href=f"/worlds/{world_id}/{section_id}",
            mark=mark,
            foot=foot,
            count=counts.get(section_id, 0),
            accent=accent,
        )
        for section_id, label, mark, foot, accent in QUICK_SECTIONS
    ]
