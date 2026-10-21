import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from ..db.db import Base
from ..db.mixins import OptimisticLockMixin, TimestampMixin, UUIDv7PrimaryKeyMixin
from ..users.models import UserModel
from .schemas import SceneFragment


class FragmentJSON(TypeDecorator[SceneFragment]):
    """The native source of a reusable asset, validated on the way in and out.

    A library asset is a scene fragment, not a flattened preview: inserting one
    has to bring editable geometry and stable identities with it.
    """

    impl = JSONB
    cache_ok = True

    def process_bind_param(self, value: SceneFragment, dialect):
        return SceneFragment.model_validate(value).model_dump(mode="json")

    def process_result_value(self, value, dialect) -> SceneFragment:
        return SceneFragment.model_validate(value)


class SceneLibraryModel(
    Base,
    UUIDv7PrimaryKeyMixin,
    TimestampMixin,
    OptimisticLockMixin,
):
    """A global library, or one belonging to a single world.

    A global library is readable and writable by an administrator. A world
    library is readable and writable by an administrator and by that world's
    master, and by nobody else: publishing artwork never widens world access.
    """

    __tablename__ = "scene_libraries"

    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    world_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("worlds.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[UserModel | None] = relationship(lazy="joined")
    sections: Mapped[list["SceneSectionModel"]] = relationship(
        back_populates="library",
        cascade="all, delete-orphan",
        order_by="SceneSectionModel.position",
        lazy="selectin",
    )


class SceneSectionModel(
    Base,
    UUIDv7PrimaryKeyMixin,
    TimestampMixin,
):
    """A named group inside a library, created by whoever manages it."""

    __tablename__ = "scene_sections"

    library_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scene_libraries.id", ondelete="CASCADE"), nullable=False
    )
    library: Mapped[SceneLibraryModel] = relationship(back_populates="sections")
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class SceneAssetModel(
    Base,
    UUIDv7PrimaryKeyMixin,
    TimestampMixin,
    OptimisticLockMixin,
):
    """One reusable authored scene fragment inside a section."""

    __tablename__ = "scene_assets"

    section_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scene_sections.id", ondelete="CASCADE"), nullable=False
    )
    section: Mapped[SceneSectionModel] = relationship(lazy="joined")
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[UserModel | None] = relationship(lazy="joined")
    fragment: Mapped[SceneFragment] = mapped_column(FragmentJSON, nullable=False)
    # Set when an admin promotes a world asset into the global library. The
    # promoted asset is a copy: existing instances keep pointing at the original,
    # so provenance is recorded rather than the link being rewritten.
    promoted_from_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("scene_assets.id", ondelete="SET NULL"), nullable=True
    )
