"""Manually interpreted landmarks from Oscar's three photos, in photo pixels.

This is a semantic vector study, not an automatic image tracing algorithm.
Every filled shape is a polygon; open ink details are polylines.
"""

from math import cos, pi, sin
from typing import Literal

from pydantic import BaseModel

INK = "#302d2b"
BLUE = "#008ed0"
BLUE_DARK = "#087dbb"
RED = "#ed2939"
CREAM = "#f5f0df"
GOLD = "#f5c632"
WOLF = "#929bb9"


class Shape(BaseModel):
    name: str
    points: list[tuple[float, float]]
    fill: str
    kind: Literal["polygon", "polyline"] = "polygon"
    stroke: str = INK
    width: float = 7


class Part(BaseModel):
    name: str
    shapes: list[Shape]


class Drawing(BaseModel):
    slug: str
    title: str
    note: str
    crop: tuple[int, int, int, int]
    parts: list[Part]


def polygon(name: str, fill: str, points: str, width: float = 7) -> Shape:
    return Shape(
        name=name,
        fill=fill,
        points=[tuple(map(float, pair.split(","))) for pair in points.split()],
        width=width,
    )


def line(name: str, points: str, width: float = 4) -> Shape:
    return polygon(name, "none", points, width).model_copy(update={"kind": "polyline"})


def oval(
    name: str, fill: str, x: float, y: float, rx: float, ry: float, width: float = 0
) -> Shape:
    # Curves are faceted deliberately, so the filled output stays polygon-only.
    return Shape(
        name=name,
        fill=fill,
        width=width,
        points=[
            (round(x + rx * cos(i * pi / 8), 2), round(y + ry * sin(i * pi / 8), 2))
            for i in range(16)
        ],
    )


DRAWINGS = [
    Drawing(
        slug="altus",
        title="Altus Fanfaròn",
        note="Senza mantello · braccia raccolte · spada verso il basso",
        crop=(175, 250, 510, 835),
        parts=[
            Part(
                name="tunic",
                shapes=[
                    polygon(
                        "torso",
                        BLUE,
                        "308,402 345,442 376,403 428,518 437,558 396,689 324,689 260,558 276,517",
                        9,
                    ),
                ],
            ),
            Part(
                name="left-coat-tail",
                shapes=[
                    polygon(
                        "left-panel",
                        BLUE,
                        "260,552 346,536 352,620 323,687 255,765 299,610",
                        8,
                    ),
                ],
            ),
            Part(
                name="right-coat-tail",
                shapes=[
                    polygon(
                        "right-panel",
                        BLUE,
                        "371,536 438,556 420,609 458,774 395,689 366,618",
                        8,
                    ),
                ],
            ),
            Part(
                name="left-arm",
                shapes=[
                    polygon(
                        "upper-arm",
                        BLUE_DARK,
                        "308,405 338,441 277,518 263,550 257,554 273,514",
                        7,
                    ),
                    polygon("forearm", BLUE, "276,518 347,517 353,528 258,561", 7),
                ],
            ),
            Part(
                name="right-arm",
                shapes=[
                    polygon(
                        "upper-arm", BLUE_DARK, "377,405 361,440 425,515 439,552", 7
                    ),
                    polygon(
                        "forearm", BLUE, "366,514 425,515 440,559 371,533 358,526", 7
                    ),
                ],
            ),
            Part(
                name="sword",
                shapes=[
                    polygon(
                        "blade", "#eee9dc", "326,568 394,567 397,771 362,815 325,771", 9
                    ),
                    polygon(
                        "blade-shadow", "#a6a9bf", "364,568 394,567 397,771 362,815", 0
                    ),
                    line("blade-ridge", "364,569 365,794 362,810", 6),
                    polygon("pommel", GOLD, "347,516 359,489 368,516", 6),
                    polygon("grip", GOLD, "351,516 368,516 369,545 350,545", 6),
                    polygon(
                        "crossguard",
                        GOLD,
                        "351,537 364,529 377,544 405,563 362,571 310,567 337,552",
                        7,
                    ),
                ],
            ),
            Part(
                name="left-hand",
                shapes=[
                    polygon(
                        "glove", BLUE, "333,524 347,519 353,524 348,533 336,538", 4
                    ),
                ],
            ),
            Part(
                name="right-hand",
                shapes=[
                    polygon("glove", BLUE, "371,521 383,528 377,537 365,530", 4),
                ],
            ),
            Part(
                name="collar",
                shapes=[
                    polygon("gold-triangle", GOLD, "309,402 376,401 346,446", 8),
                ],
            ),
            Part(
                name="crest",
                shapes=[
                    polygon("upper-feather", RED, "264,278 216,298 267,316", 8),
                    polygon("middle-feather", RED, "266,316 218,331 269,354", 8),
                    polygon("lower-feather", RED, "270,354 220,374 274,398", 8),
                ],
            ),
            Part(
                name="head",
                shapes=[
                    polygon(
                        "head-and-hooked-beak",
                        BLUE,
                        "267,275 444,377 457,427 430,396 274,401",
                        10,
                    ),
                    line("beak-seam", "378,359 420,380", 5),
                ],
            ),
            Part(
                name="eye",
                shapes=[
                    polygon("eye-field", CREAM, "292,318 299,362 354,362", 6),
                    oval("pupil", INK, 311, 347, 12, 17),
                    oval("eye-highlight", CREAM, 309, 347, 6, 10),
                ],
            ),
        ],
    ),
    Drawing(
        slug="luciano",
        title="Luciano Piumalesta",
        note="Corpo ottagonale · ali separate · strisce come poligoni",
        crop=(150, 315, 500, 790),
        parts=[
            Part(
                name="left-foot",
                shapes=[
                    polygon("left-leg", GOLD, "273,702 296,707 274,736 267,738", 5),
                    polygon(
                        "left-toes",
                        GOLD,
                        "273,733 281,746 291,760 278,754 268,769 267,750 251,757",
                        5,
                    ),
                ],
            ),
            Part(
                name="right-foot",
                shapes=[
                    polygon("right-leg", GOLD, "362,704 379,705 379,738 372,739", 5),
                    polygon(
                        "right-toes",
                        GOLD,
                        "375,734 389,737 402,746 388,745 388,755 379,748 370,761 369,749",
                        5,
                    ),
                ],
            ),
            Part(
                name="body",
                shapes=[
                    polygon(
                        "octagon",
                        RED,
                        "288,499 383,514 438,562 448,629 381,710 271,712 198,612 221,544",
                        8,
                    ),
                ],
            ),
            Part(
                name="stripes",
                shapes=[
                    polygon("stripe-1", CREAM, "238,533 250,526 229,654 218,639", 5),
                    polygon("stripe-2", CREAM, "298,503 314,508 272,710 261,698", 6),
                    polygon("stripe-3", CREAM, "358,515 375,519 330,710 313,711", 6),
                    polygon("stripe-4", CREAM, "402,574 416,589 398,689 381,710", 6),
                ],
            ),
            Part(
                name="head-and-neck",
                shapes=[
                    polygon(
                        "bird-profile",
                        BLUE,
                        "273,423 308,377 347,366 368,377 378,398 370,413 368,438 383,454 368,522 297,509 305,456 329,440 328,414 309,415",
                        7,
                    ),
                    line("beak-seam", "290,414 301,407 305,398", 4),
                ],
            ),
            Part(
                name="eye",
                shapes=[
                    polygon("eye-field", CREAM, "318,389 342,380 334,394 321,394", 4),
                    polygon("pupil", INK, "327,386 338,383 331,392 325,392", 0),
                ],
            ),
            Part(
                name="left-strap",
                shapes=[
                    polygon("red-strap", RED, "294,452 307,451 296,509 284,507", 5),
                ],
            ),
            Part(
                name="right-strap",
                shapes=[
                    polygon("red-strap", RED, "379,452 391,459 377,527 366,522", 5),
                ],
            ),
            Part(
                name="left-wing",
                shapes=[
                    polygon("upper-triangle", BLUE, "173,439 296,453 227,515", 8),
                    polygon("fold", BLUE_DARK, "227,515 289,469 283,508 221,543", 6),
                ],
            ),
            Part(
                name="right-wing",
                shapes=[
                    polygon("wing-tip", BLUE_DARK, "410,574 451,616 438,635", 6),
                    polygon("wing", BLUE, "395,462 477,542 468,627 398,581", 8),
                ],
            ),
            Part(
                name="cap",
                shapes=[
                    oval("red-button", RED, 371, 342, 8, 9, 5),
                    polygon(
                        "white-cap",
                        CREAM,
                        "347,366 332,364 325,359 325,353 332,348 349,347 367,350 381,357 393,371 402,386 402,393 395,400 385,402 378,398 373,386 368,377 357,369",
                        6,
                    ),
                ],
            ),
        ],
    ),
    Drawing(
        slug="wolf",
        title="Tacito · Genio dell’assalto",
        note="Braccia alzate · gambe piegate · spada dietro il corpo",
        crop=(160, 245, 620, 865),
        parts=[
            Part(
                name="sword",
                shapes=[
                    polygon(
                        "blade", "#e9e8dc", "230,391 287,339 570,623 579,713 503,690", 8
                    ),
                    polygon("blade-bevel", "#b9bdb8", "260,366 570,625 579,713", 0),
                    polygon(
                        "blade-light", "#f7f4e8", "260,366 539,672 503,690 230,391", 0
                    ),
                    line("blade-ridge", "260,366 539,672 579,713", 4),
                    polygon("handle", RED, "182,272 195,263 254,322 235,340", 8),
                    polygon(
                        "guard",
                        RED,
                        "210,365 277,308 313,309 317,317 217,399 208,390",
                        8,
                    ),
                ],
            ),
            Part(
                name="left-boot",
                shapes=[
                    polygon(
                        "boot", "#9e5736", "310,787 349,789 350,843 270,847 305,816", 8
                    ),
                    line("cuff", "310,803 347,803", 4),
                    line("sole", "282,837 347,834", 4),
                ],
            ),
            Part(
                name="right-boot",
                shapes=[
                    polygon(
                        "boot", "#9e5736", "425,793 459,794 466,817 505,846 428,844", 8
                    ),
                    line("cuff", "429,808 460,807", 4),
                    line("sole", "430,835 491,836", 4),
                ],
            ),
            Part(
                name="left-leg",
                shapes=[
                    polygon(
                        "trousers",
                        RED,
                        "330,651 393,658 397,680 351,739 348,790 308,794 296,737",
                        8,
                    ),
                ],
            ),
            Part(
                name="right-leg",
                shapes=[
                    polygon(
                        "trousers",
                        RED,
                        "392,657 448,655 474,725 458,797 422,798 434,741 394,683",
                        8,
                    ),
                    polygon(
                        "side-shadow",
                        "#d52134",
                        "447,667 465,725 449,784 433,787 445,735",
                        0,
                    ),
                ],
            ),
            Part(
                name="torso",
                shapes=[
                    polygon(
                        "body",
                        WOLF,
                        "329,451 454,451 476,502 462,554 450,646 330,640 314,536 314,493",
                        8,
                    ),
                ],
            ),
            Part(
                name="belly",
                shapes=[
                    polygon(
                        "belly-patch",
                        CREAM,
                        "361,518 427,516 442,546 445,640 334,637 345,543",
                        7,
                    ),
                    line("scar", "360,614 413,543", 3.5),
                    line("stitch-1", "362,599 371,611", 3),
                    line("stitch-2", "371,588 381,600", 3),
                    line("stitch-3", "380,575 391,589", 3),
                    line("stitch-4", "389,564 400,578", 3),
                    line("stitch-5", "399,552 410,566", 3),
                ],
            ),
            Part(
                name="left-arm-and-hand",
                shapes=[
                    polygon(
                        "raised-arm",
                        WOLF,
                        "329,453 345,478 354,493 297,565 211,477 195,450 198,431 209,423 221,422 216,438 224,444 233,423 243,426 234,445 242,461 249,461 254,443 263,448 266,458 258,475 296,510",
                        8,
                    ),
                    # Cover the shared shoulder edge to keep the original continuous silhouette.
                    polygon(
                        "shoulder-join",
                        WOLF,
                        "331,456 344,466 355,483 347,497 318,478",
                        0,
                    ),
                ],
            ),
            Part(
                name="right-arm-and-hand",
                shapes=[
                    polygon(
                        "raised-arm",
                        WOLF,
                        "454,453 483,516 537,493 530,474 536,459 549,473 561,466 560,446 553,443 570,439 583,445 592,453 595,465 585,496 483,565 438,498",
                        8,
                    ),
                    polygon(
                        "shoulder-join",
                        WOLF,
                        "450,457 460,465 476,497 464,517 440,487",
                        0,
                    ),
                    line("finger-fold-1", "572,446 580,458 578,464", 4),
                    line("finger-fold-2", "583,449 588,460", 4),
                ],
            ),
            Part(
                name="chest-scar",
                shapes=[
                    line("scar", "407,494 434,476", 3),
                    line("stitch-1", "411,484 416,498", 3),
                    line("stitch-2", "418,479 424,493", 3),
                    line("stitch-3", "426,475 431,487", 3),
                ],
            ),
            Part(
                name="belt",
                shapes=[
                    polygon("leather", "#a6542d", "335,638 444,642 451,664 327,659", 7),
                    line("belt-seam", "334,649 444,653", 3),
                    polygon(
                        "green-buckle",
                        "#69a32b",
                        "372,631 382,630 384,640 390,640 391,632 402,635 403,660 370,664 368,644 375,644",
                        6,
                    ),
                ],
            ),
            Part(
                name="head",
                shapes=[
                    polygon(
                        "wolf-profile",
                        WOLF,
                        "326,339 343,311 373,338 436,337 456,311 472,350 478,368 498,359 512,369 504,423 461,452 327,453 313,428 309,410 323,418 317,394 326,402",
                        8,
                    ),
                    line("snout-top", "439,386 496,363", 7),
                    polygon("nose", INK, "497,360 511,369 506,389 497,389 493,376", 3),
                ],
            ),
            Part(
                name="eyes",
                shapes=[
                    polygon("left-eye", CREAM, "357,353 384,359 397,377 367,371", 4),
                    polygon("right-eye", CREAM, "427,357 454,351 448,371 421,378", 4),
                    line("left-brow", "373,343 384,345 394,363", 5),
                    line("right-brow", "423,351 431,342", 5),
                ],
            ),
            Part(
                name="mouth",
                shapes=[
                    polygon("teeth-field", CREAM, "446,403 503,389 502,423 446,431", 6),
                    line("teeth", "450,403 465,426 472,397 486,425 493,393", 3),
                ],
            ),
            Part(
                name="muzzle-marks",
                shapes=[
                    line(
                        "curl",
                        "365,387 368,383 362,379 355,378 349,382 349,390 354,397 363,401 380,400 394,403 405,410 409,418 406,425 399,428 391,427 387,423 391,419 397,420",
                        3.5,
                    ),
                    line("diagonal", "364,423 391,381", 3.5),
                ],
            ),
        ],
    ),
]
