"""The reusable-asset contract.

An asset stores a **scene fragment**: the native nodes a drawing editor wrote,
with their stable identities, constraints, styles and anchors intact. It is
deliberately not a rendered preview, so inserting an asset produces editable
artwork and never a flattened picture.
"""

from datetime import datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import Field, model_validator

from ..drawings.schemas import MAX_NODES, SCENE_FORMAT_VERSION, GroupNode, Node
from ..schemas import AppBaseModel, TimestampMixin, UUIDField

DOMAIN = {"extra": "forbid", "populate_by_name": True}


class LibraryScope(str, Enum):
    """Who a library belongs to, and therefore who may read it."""

    GLOBAL = "global"
    WORLD = "world"


def fragment_node_count(nodes: list[Node]) -> int:
    """Every node in the fragment, groups included."""
    return sum(
        1 + (fragment_node_count(node.nodes) if isinstance(node, GroupNode) else 0)
        for node in nodes
    )


class SceneFragment(AppBaseModel):
    """A subtree lifted out of a drawing, ready to be inserted into another."""

    model_config = AppBaseModel.model_config | DOMAIN

    schema_version: Literal[SCENE_FORMAT_VERSION] = SCENE_FORMAT_VERSION
    nodes: Annotated[list[Node], Field(min_length=1, max_length=MAX_NODES)]

    @model_validator(mode="after")
    def _identities_are_unique(self) -> SceneFragment:
        seen: set[str] = set()

        def visit(nodes: list[Node], depth: int) -> None:
            if depth > 8:
                raise ValueError("fragment is nested too deeply")
            for node in nodes:
                if node.id in seen:
                    raise ValueError("fragment identities must be unique")
                seen.add(node.id)
                if isinstance(node, GroupNode):
                    visit(node.nodes, depth + 1)

        visit(self.nodes, 0)
        if fragment_node_count(self.nodes) > MAX_NODES:
            raise ValueError("fragment has too many nodes")
        return self


class SectionCreate(AppBaseModel):
    model_config = AppBaseModel.model_config | DOMAIN

    name: Annotated[str, Field(min_length=1, max_length=120)]


class SectionResponse(TimestampMixin):
    model_config = AppBaseModel.model_config | DOMAIN

    id: UUIDField
    name: str
    position: int
    asset_count: int = 0


class AssetCreate(AppBaseModel):
    model_config = AppBaseModel.model_config | DOMAIN

    section_id: UUIDField
    name: Annotated[str, Field(min_length=1, max_length=255)]
    fragment: SceneFragment


class AssetUpdate(AppBaseModel):
    model_config = AppBaseModel.model_config | DOMAIN

    expected_version: Annotated[int, Field(ge=1)]
    name: Annotated[str, Field(min_length=1, max_length=255)] | None = None
    section_id: UUIDField | None = None
    fragment: SceneFragment | None = None


class AssetSummary(AppBaseModel):
    """Bounded metadata for a listing: no geometry crosses the wire."""

    model_config = AppBaseModel.model_config | DOMAIN

    id: UUIDField
    name: str
    section_id: UUIDField
    section_name: str
    node_count: int
    version: int
    updated_at: datetime


class AssetResponse(AssetSummary):
    fragment: SceneFragment


class LibraryCreate(AppBaseModel):
    model_config = AppBaseModel.model_config | DOMAIN

    name: Annotated[str, Field(min_length=1, max_length=255)]
    scope: LibraryScope
    world_id: UUIDField | None = None

    @model_validator(mode="after")
    def _scope_and_world_agree(self) -> LibraryCreate:
        world_scope = LibraryScope(self.scope) is LibraryScope.WORLD
        if world_scope != (self.world_id is not None):
            raise ValueError("a world library needs a world and a global one does not")
        return self


class LibraryResponse(TimestampMixin):
    model_config = AppBaseModel.model_config | DOMAIN

    id: UUIDField
    name: str
    scope: LibraryScope
    world_id: UUIDField | None = None
    version: int
    sections: list[SectionResponse] = Field(default_factory=list)
