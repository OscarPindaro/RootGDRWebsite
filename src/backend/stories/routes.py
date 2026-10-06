import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import get_current_user
from ..dependencies import get_db_session
from ..schemas import ListResponse
from ..users.schemas import User
from .models import StoryModel
from .schemas import (
    StoryCreate,
    StoryResponse,
    StorySessionReference,
    StorySummary,
    StoryUpdate,
)
from .service import (
    create_story,
    delete_story,
    get_story,
    list_stories,
    update_story,
)

router = APIRouter(prefix="/api/worlds/{world_id}/stories", tags=["stories"])


def _to_response(story: StoryModel, user: User) -> StoryResponse:
    """The story with the composed sessions this reader may see.

    A draft session stays its author's, in the reference list as everywhere
    else: a reader never learns its title through a story.
    """
    response = StoryResponse.model_validate(story)
    response.sessions = [
        StorySessionReference.model_validate(session)
        for session in story.sessions
        if not session.is_draft or session.created_by_id == user.id
    ]
    return response


@router.post("/", response_model=StoryResponse, status_code=status.HTTP_201_CREATED)
async def create_story_route(
    world_id: uuid.UUID,
    data: StoryCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> StoryResponse:
    """Create a story (master only)."""
    return _to_response(await create_story(db, world_id, data, user), user)


@router.get("/", response_model=ListResponse[StorySummary])
async def list_stories_route(
    world_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> ListResponse[StorySummary]:
    """List the stories of an accessible world, in creation order."""
    stories = await list_stories(db, world_id, user)
    return ListResponse(data=[StorySummary.model_validate(s) for s in stories])


@router.get("/{story_id}", response_model=StoryResponse)
async def get_story_route(
    world_id: uuid.UUID,
    story_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> StoryResponse:
    """Return one story."""
    return _to_response(await get_story(db, world_id, story_id, user), user)


@router.patch("/{story_id}", response_model=StoryResponse)
async def update_story_route(
    world_id: uuid.UUID,
    story_id: uuid.UUID,
    data: StoryUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> StoryResponse:
    """Update a story (master only)."""
    return _to_response(await update_story(db, world_id, story_id, data, user), user)


@router.delete("/{story_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_story_route(
    world_id: uuid.UUID,
    story_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> None:
    """Delete a story (master only)."""
    await delete_story(db, world_id, story_id, user)
