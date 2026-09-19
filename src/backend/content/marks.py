"""Server-side role marks: a linear icon or an equivalent solid shape.

The prototype defined these in JavaScript and swapped them in the browser. Here
they are rendered on the server so the first paint is already correct and the
reading page needs no JavaScript. A component references a *role*
(``personaggi``, ``luoghi``, ...) and the role resolves to the mark for the
active symbol style.
"""

from markupsafe import Markup

from .constants import ContentKind

# ---------- linear icons ----------
ICONS: dict[str, str] = {
    "globo": (
        '<circle cx="12" cy="12" r="9"/>'
        '<ellipse cx="12" cy="12" rx="4" ry="9"/>'
        '<line x1="3" y1="12" x2="21" y2="12"/>'
    ),
    "orologio": (
        '<circle cx="12" cy="12" r="9"/><polyline points="12,6.5 12,12 16,14.5"/>'
    ),
    "persona": (
        '<circle cx="12" cy="8" r="3.6"/><path d="M4.8 20.4a7.2 7.2 0 0 1 14.4 0"/>'
    ),
    "bussola": (
        '<circle cx="12" cy="12" r="9"/><polygon points="12,6 14.6,15 12,13.4 9.4,15"/>'
    ),
    "pin": (
        '<path d="M12 21s7-6.2 7-11a7 7 0 1 0-14 0c0 4.8 7 11 7 11z"/>'
        '<circle cx="12" cy="10" r="2.6"/>'
    ),
    "calendario": (
        '<rect x="3" y="5.5" width="18" height="15.5"/>'
        '<line x1="3" y1="10.5" x2="21" y2="10.5"/>'
        '<line x1="8" y1="3" x2="8" y2="7.5"/>'
        '<line x1="16" y1="3" x2="16" y2="7.5"/>'
    ),
    "libro": (
        '<path d="M4 5.6A2.6 2.6 0 0 1 6.6 3H19.5v15.5H6.6A2.6 2.6 0 0 0 4 21z"/>'
        '<line x1="8.5" y1="7.8" x2="15.5" y2="7.8"/>'
        '<line x1="8.5" y1="11.4" x2="15.5" y2="11.4"/>'
    ),
    "documento": (
        '<path d="M6 3h8l4.5 4.5V21H6z"/>'
        '<polyline points="14,3 14,7.5 18.5,7.5"/>'
        '<line x1="9" y1="12.5" x2="15" y2="12.5"/>'
        '<line x1="9" y1="16" x2="15" y2="16"/>'
    ),
    "utenti": (
        '<circle cx="9" cy="8.6" r="3.2"/>'
        '<path d="M3.2 19.8a5.8 5.8 0 0 1 11.6 0"/>'
        '<path d="M16.4 6.4a3 3 0 0 1 0 5.4"/>'
        '<path d="M18 19.8a5.6 5.6 0 0 0-2.5-4.6"/>'
    ),
}

# ---------- solid shapes ----------
SHAPES: dict[str, str] = {
    "cerchio": '<circle cx="12" cy="12" r="9.5"/>',
    "quadrato": '<rect x="2.5" y="2.5" width="19" height="19"/>',
    "triangolo": '<polygon points="12,2.5 22,21.5 2,21.5"/>',
    "rombo": '<polygon points="12,2 22,12 12,22 2,12"/>',
    "esagono": '<polygon points="12,2 21.5,7.5 21.5,16.5 12,22 2.5,16.5 2.5,7.5"/>',
    "pentagono": '<polygon points="12,2 22,9.6 18.2,21 5.8,21 2,9.6"/>',
    "stella": (
        '<polygon points="12,2 14.65,8.36 21.51,8.91 16.28,13.39 17.88,20.09 '
        '12,16.5 6.12,20.09 7.72,13.39 2.49,8.91 9.35,8.36"/>'
    ),
    "croce": '<path d="M9 2h6v7h7v6h-7v7H9v-7H2V9h7z"/>',
    "ottagono": (
        '<polygon points="20.78,15.64 15.64,20.78 8.36,20.78 3.22,15.64 '
        '3.22,8.36 8.36,3.22 15.64,3.22 20.78,8.36"/>'
    ),
    "semicerchio": '<path d="M2 15.5a10 10 0 0 1 20 0z"/>',
    "goccia": '<path d="M12 2c0 0 7 8.2 7 13a7 7 0 0 1-14 0c0-4.8 7-13 7-13z"/>',
    "anello": (
        '<path fill-rule="evenodd" d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm0 '
        '5.5a4.5 4.5 0 1 1 0 9 4.5 4.5 0 0 1 0-9z"/>'
    ),
}

# Every role has an equivalent icon and shape.
BY_ROLE: dict[str, tuple[str, str]] = {
    "mondi": ("globo", "cerchio"),
    "attivita": ("orologio", "rombo"),
    "profilo": ("persona", "quadrato"),
    "mondo": ("bussola", "cerchio"),
    "personaggi": ("persona", "quadrato"),
    "personaggio": ("persona", "quadrato"),
    "npc": ("utenti", "ottagono"),
    "luoghi": ("pin", "triangolo"),
    "luogo": ("pin", "triangolo"),
    "sessioni": ("calendario", "rombo"),
    "sessione": ("calendario", "rombo"),
    "storie": ("libro", "esagono"),
    "storia": ("libro", "esagono"),
    "pagine": ("documento", "pentagono"),
    "pagina": ("documento", "anello"),
}

KIND_ICON: dict[ContentKind, str] = {
    ContentKind.CHARACTER: "persona",
    ContentKind.NPC: "utenti",
    ContentKind.PLACE: "pin",
    ContentKind.SESSION: "calendario",
    ContentKind.STORY: "libro",
    ContentKind.PAGE: "documento",
}


def icon_svg(name: str) -> str:
    body = ICONS.get(name, ICONS["persona"])
    return (
        '<svg class="mark__svg" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="1.6" stroke-linecap="round" '
        'stroke-linejoin="round" aria-hidden="true">' + body + "</svg>"
    )


def shape_svg(name: str) -> str:
    body = SHAPES.get(name, SHAPES["cerchio"])
    return (
        '<svg class="mark__svg mark__svg--shape" viewBox="0 0 24 24" '
        'fill="currentColor" aria-hidden="true">' + body + "</svg>"
    )


def mark_svg(role: str, style: str = "icons") -> Markup:
    """Return the SVG for a role in the requested symbol style."""
    icon, shape = BY_ROLE.get(role, BY_ROLE["pagina"])
    body = shape_svg(shape) if style == "shapes" else icon_svg(icon)
    return Markup(body)


def kind_svg(kind: str, style: str = "icons") -> Markup:
    """Return the SVG for a content kind (used by references)."""
    try:
        parsed = ContentKind(kind)
    except ValueError:
        parsed = ContentKind.PAGE
    return mark_svg(parsed.value, style)


def shape_mark(name: str) -> Markup:
    """Return the SVG for a fixed shape (places)."""
    return Markup(shape_svg(name))
