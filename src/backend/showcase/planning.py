"""Typed, database-free fixtures for the dev-only frontend planning study."""

from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from jinjax.catalog import Catalog
from pydantic import BaseModel, Field

from ..dependencies import get_catalog_dep
from ..navigation import NavItem, Option

router = APIRouter(tags=["showcase"])
StudyView = Literal[
    "story",
    "npcs",
    "places",
    "character",
    "session",
    "assistant",
    "evaluation",
    "history",
    "settings",
]


class StudyTrack(BaseModel):
    key: str
    label: str
    capacity: int = Field(ge=0, le=8)
    marked: int = Field(ge=0)


class StudyMove(BaseModel):
    title: str
    description: str = ""


class StudyNpc(BaseModel):
    key: str
    name: str
    role: str
    tint: str
    description: str
    motivation: str
    wants: str
    accepts: str
    damage: str
    equipment: str = ""
    tracks: list[StudyTrack]
    moves: list[StudyMove]


class StudyPlace(BaseModel):
    name: str
    kind: str
    container: str
    controller: str
    description: str


class StudyCheck(BaseModel):
    name: str
    expected: str
    observed: str
    kind: Literal["Esatto", "Giudice"]


class PlanningStudy(BaseModel):
    view: StudyView
    title: str
    nav: list[NavItem]
    choices: list[Option]
    npcs: list[StudyNpc]
    places: list[StudyPlace]
    character_tracks: list[StudyTrack]
    checks: list[StudyCheck]


def planning_study(view: StudyView = "story") -> PlanningStudy:
    labels = [
        ("story", "Storia", "storie"),
        ("npcs", "NPC", "npc"),
        ("places", "Luoghi e fazioni", "luoghi"),
        ("character", "Personaggio", "personaggi"),
        ("session", "Sessione", "sessioni"),
        ("assistant", "Assistente e fonti", "pagina"),
        ("evaluation", "Valutazione", "storie"),
        ("history", "Storico e recupero", "sessioni"),
        ("settings", "Prompt e modelli", "mondo"),
    ]
    return PlanningStudy(
        view=view,
        title="Ritorno a Borgo Mulino"
        if view == "story"
        else next(label for key, label, _mark in labels if key == view),
        nav=[
            NavItem(
                id=key,
                label=label,
                href=f"/components/planning?view={key}",
                mark=mark,
            )
            for key, label, mark in labels
        ],
        choices=[Option(value=key, label=label) for key, label, _mark in labels],
        checks=[
            StudyCheck(
                name="Personaggi creati",
                expected="Esattamente 1",
                observed="1",
                kind="Esatto",
            ),
            StudyCheck(
                name="Nome del personaggio",
                expected="Neri",
                observed="Neri",
                kind="Esatto",
            ),
            StudyCheck(
                name="Altri oggetti modificati",
                expected="Nessuno",
                observed="Nessuno",
                kind="Esatto",
            ),
            StudyCheck(
                name="Fedelta e stile",
                expected="Rubrica v1",
                observed="4/5 illustrativo",
                kind="Giudice",
            ),
        ],
        places=[
            StudyPlace(
                name="Borgo Mulino",
                kind="Radura",
                container="Luogo indipendente",
                controller="Abitanti",
                description="Il contesto geografico resta disponibile anche quando la storia finisce.",
            ),
            StudyPlace(
                name="Il mulino",
                kind="Edificio",
                container="Dentro Borgo Mulino",
                controller="Abitanti",
                description="Un luogo specifico, collegato alla radura senza copiarne la descrizione.",
            ),
            StudyPlace(
                name="Il tempio nel bosco",
                kind="Tempio",
                container="Nel bosco, vicino a due radure",
                controller="Non registrato",
                description="Due fazioni lo rivendicano. Questo non significa che lo controllino entrambe.",
            ),
        ],
        character_tracks=[
            StudyTrack(key="fatigue", label="Fatica", capacity=4, marked=1),
            StudyTrack(key="wounds", label="Ferite", capacity=4, marked=0),
            StudyTrack(key="wear", label="Usura", capacity=3, marked=1),
            StudyTrack(key="depletion", label="Consumo", capacity=4, marked=2),
        ],
        npcs=[
            StudyNpc(
                key="ada",
                name="Ada",
                role="Custode del mulino",
                tint="p2",
                description="Conosce ogni rumore delle macine. Prima ascolta, poi risponde.",
                motivation="Proteggere il lavoro degli abitanti.",
                wants="Rimettere in moto il mulino.",
                accepts="Aspettare, se qualcuno garantisce il prossimo carico.",
                damage="1 ferita",
                equipment="Chiavi del mulino, registro delle consegne.",
                tracks=[
                    StudyTrack(key="fatigue", label="Fatica", capacity=3, marked=1),
                    StudyTrack(key="wounds", label="Ferite", capacity=2, marked=0),
                    StudyTrack(key="wear", label="Usura", capacity=2, marked=0),
                    StudyTrack(key="morale", label="Morale", capacity=4, marked=1),
                ],
                moves=[
                    StudyMove(
                        title="Conoscere il lavoro",
                        description="Indica chi ha toccato un meccanismo e cosa manca per ripararlo.",
                    ),
                    StudyMove(title="Chiedere una garanzia"),
                ],
            ),
            StudyNpc(
                key="patrol",
                name="La pattuglia del ponte",
                role="Gruppo di abitanti",
                tint="p4",
                description="Quattro abitanti sorvegliano il passaggio. Non cercano una battaglia.",
                motivation="Tenere aperta la strada dei rifornimenti.",
                wants="Un passaggio sicuro per il prossimo carico.",
                accepts="Una tregua con condizioni chiare.",
                damage="2 ferite",
                tracks=[
                    StudyTrack(key="fatigue", label="Fatica", capacity=2, marked=0),
                    StudyTrack(key="wounds", label="Ferite", capacity=4, marked=1),
                    StudyTrack(key="morale", label="Morale", capacity=3, marked=0),
                ],
                moves=[
                    StudyMove(title="Chiudere il passaggio"),
                    StudyMove(
                        title="Cercare un accordo",
                        description="Offrono una via d'uscita prima di rischiare la vita degli altri.",
                    ),
                ],
            ),
        ],
    )


@router.get("/components/planning", response_class=HTMLResponse)
async def planning_page(
    view: StudyView = "story",
    catalog: Catalog = Depends(get_catalog_dep),
) -> HTMLResponse:
    study = planning_study(view)
    return catalog.render("pages.showcase.Planning", study=study)


@router.get("/components/planning/npc/{npc_key}", response_class=HTMLResponse)
async def planning_npc_fragment(
    npc_key: Literal["ada", "patrol"],
    catalog: Catalog = Depends(get_catalog_dep),
) -> HTMLResponse:
    npc = next(npc for npc in planning_study().npcs if npc.key == npc_key)
    return catalog.render("pages.showcase.PlanningNpc", npc=npc)
