"""Shared vocabulary for content identity.

Tints, shapes and animals are validated here so no feature invents its own
values. A tint is a token name (``p1``..``p12``); a shape is one of the twelve
geometric names; an animal is an emoji.
"""

from enum import Enum
from typing import Literal

TINTS: tuple[str, ...] = tuple(f"p{i}" for i in range(1, 13))
Tint = Literal[
    "p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8", "p9", "p10", "p11", "p12"
]

SHAPE_NAMES: tuple[str, ...] = (
    "cerchio",
    "quadrato",
    "triangolo",
    "rombo",
    "esagono",
    "pentagono",
    "stella",
    "croce",
    "ottagono",
    "semicerchio",
    "goccia",
    "anello",
)
Shape = Literal[
    "cerchio",
    "quadrato",
    "triangolo",
    "rombo",
    "esagono",
    "pentagono",
    "stella",
    "croce",
    "ottagono",
    "semicerchio",
    "goccia",
    "anello",
]

ANIMALS: tuple[str, ...] = (
    "🐈",
    "🦫",
    "🦌",
    "🐦‍⬛",
    "🦡",
    "🦎",
    "🐿️",
    "🦉",
    "🐺",
    "🦊",
    "🐍",
    "🐢",
    "🐝",
    "🦇",
    "🐸",
    "🐁",
)

DEFAULT_TINT: Tint = "p1"
DEFAULT_SHAPE: Shape = "cerchio"
DEFAULT_ANIMAL: str = "🐈"

TINT_LABELS: dict[str, str] = {
    "p1": "Vermiglio",
    "p2": "Arancio",
    "p3": "Ocra",
    "p4": "Oliva",
    "p5": "Bosco",
    "p6": "Turchese",
    "p7": "Cielo",
    "p8": "Cobalto",
    "p9": "Indaco",
    "p10": "Prugna",
    "p11": "Rosa",
    "p12": "Argilla",
}

SHAPE_LABELS: dict[str, str] = {
    "cerchio": "Cerchio",
    "quadrato": "Quadrato",
    "triangolo": "Triangolo",
    "rombo": "Rombo",
    "esagono": "Esagono",
    "pentagono": "Pentagono",
    "stella": "Stella",
    "croce": "Croce",
    "ottagono": "Ottagono",
    "semicerchio": "Semicerchio",
    "goccia": "Goccia",
    "anello": "Anello",
}


class ContentKind(str, Enum):
    """The kinds of document that can be referenced and linked."""

    CHARACTER = "personaggio"
    NPC = "npc"
    PLACE = "luogo"
    SESSION = "sessione"
    STORY = "storia"
    PAGE = "pagina"


KIND_LABELS: dict[ContentKind, str] = {
    ContentKind.CHARACTER: "Personaggio",
    ContentKind.NPC: "NPC",
    ContentKind.PLACE: "Luogo",
    ContentKind.SESSION: "Sessione",
    ContentKind.STORY: "Storia",
    ContentKind.PAGE: "Pagina",
}
