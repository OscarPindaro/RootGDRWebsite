import re
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .client import BoardClient, BoardError, BoardLabel, BoardLabelSpec, BoardTask
from .requests import REPO_ROOT

CATALOGUE = REPO_ROOT / ".devin/backlog-labels.yaml"


class LabelCatalogue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    labels: list[BoardLabelSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def valid_names(self) -> "LabelCatalogue":
        titles = [label.title for label in self.labels]
        if len(set(titles)) != len(titles) or any(
            not re.fullmatch(r"(?:type|area):[a-z]+(?:-[a-z]+)*", title)
            for title in titles
        ):
            raise ValueError("Catalogue labels require unique type:/area: names")
        return self

    def resolve(self, title: str) -> BoardLabelSpec:
        for label in self.labels:
            if label.title == title:
                return label
        raise BoardError("Type or area is not in the approved label catalogue")


def load_catalogue(path: Path = CATALOGUE) -> LabelCatalogue:
    return LabelCatalogue.model_validate(
        yaml.safe_load(path.read_text(encoding="utf-8"))
    )


class CatalogueReceipt(BaseModel):
    labels: list[BoardLabel] = Field(default_factory=list)
    complete: bool = True


class ClassificationReceipt(BaseModel):
    task: BoardTask
    added_labels: list[str] = Field(default_factory=list)
    type_preserved: bool = False
    colour_preserved: bool = False


def classify_task(
    board: BoardClient,
    catalogue: LabelCatalogue,
    task_id: int,
    project: int,
    kind: str,
    areas: list[str],
    *,
    replace_colour: bool = False,
) -> ClassificationReceipt:
    requested = catalogue.resolve("type:" + kind)
    area_specs = [catalogue.resolve("area:" + area) for area in areas]
    task = board.task(task_id)
    if task.project_id != project:
        raise BoardError(
            "Task belongs to a different project; classification was not changed"
        )
    attached = board.task_labels(task_id)
    types = [label for label in attached if label.title.startswith("type:")]
    if len(types) > 1:
        raise BoardError("Multiple primary type labels require owner review")
    primary = catalogue.resolve(types[0].title) if types else requested
    selected = {spec.title: spec for spec in [primary, *area_specs]}
    available = board.labels()
    resolved: list[BoardLabel] = []
    for spec in selected.values():
        matches = [label for label in available if label.title == spec.title]
        if len(matches) != 1 or matches[0].hex_color != spec.hex_color:
            raise BoardError(
                "Required labels are missing, ambiguous or differ from the catalogue; review labels --ensure first"
            )
        resolved.append(matches[0])
    receipt = ClassificationReceipt(
        task=task,
        type_preserved=bool(types and primary.title != requested.title),
        colour_preserved=bool(
            task.hex_color
            and task.hex_color != primary.hex_color
            and not replace_colour
        ),
    )
    for label in resolved:
        if board.add_label_once(task_id, label.id):
            receipt.added_labels.append(label.title)
    if (not task.hex_color or replace_colour) and task.hex_color != primary.hex_color:
        board.set_task_colour(task_id, primary.hex_color)
    receipt.task = board.task(task_id)
    receipt.task.labels = board.task_labels(task_id)
    final_types = [
        label.title for label in receipt.task.labels if label.title.startswith("type:")
    ]
    final_titles = {label.title for label in receipt.task.labels}
    if final_types != [primary.title] or not set(selected).issubset(final_titles):
        raise BoardError(
            "Classification read-back differs; review concurrent changes before retrying",
            ambiguous=True,
        )
    if not receipt.colour_preserved and receipt.task.hex_color != primary.hex_color:
        raise BoardError(
            "Classification colour read-back differs; inspect before retrying",
            ambiguous=True,
        )
    return receipt
