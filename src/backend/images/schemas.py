import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from .models import ImageOwnerKind, ImageRevisionModel


class ImageOwner(BaseModel):
    world_id: uuid.UUID
    kind: ImageOwnerKind
    owner_id: uuid.UUID


class ImageRevisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    world_id: uuid.UUID
    owner_kind: ImageOwnerKind
    owner_id: uuid.UUID
    file_id: uuid.UUID
    filename: str
    uploaded_by_id: uuid.UUID | None
    uploaded_by_name: str | None
    created_at: datetime
    updated_at: datetime
    is_current: bool

    @classmethod
    def from_revision(
        cls, revision: ImageRevisionModel, current_file_id: uuid.UUID | None
    ) -> "ImageRevisionResponse":
        return cls(
            id=revision.id,
            world_id=revision.world_id,
            owner_kind=revision.owner_kind,
            owner_id=revision.owner_id,
            file_id=revision.file_id,
            filename=revision.file.name,
            uploaded_by_id=revision.uploaded_by_id,
            uploaded_by_name=(
                revision.uploaded_by.name if revision.uploaded_by else None
            ),
            created_at=revision.created_at,
            updated_at=revision.updated_at,
            is_current=revision.file_id == current_file_id,
        )
