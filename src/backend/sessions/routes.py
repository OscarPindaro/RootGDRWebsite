import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import get_current_user
from ..dependencies import get_db_session
from ..schemas import ListResponse
from ..users.schemas import User
from .models import SessionModel
from .schemas import SessionCreate, SessionResponse, SessionSummary, SessionUpdate
from .service import (
    create_session,
    delete_session,
    get_session,
    list_sessions,
    update_session,
)

router = APIRouter(prefix="/api/worlds/{world_id}/sessions", tags=["sessions"])


def _to_response(session: SessionModel) -> SessionResponse:
    return SessionResponse.model_validate(session)


@router.post("/", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session_route(
    world_id: uuid.UUID,
    data: SessionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> SessionResponse:
    """Create a session (master only)."""
    return _to_response(await create_session(db, world_id, data, user))


@router.get("/", response_model=ListResponse[SessionSummary])
async def list_sessions_route(
    world_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> ListResponse[SessionSummary]:
    """List the sessions of an accessible world, oldest first."""
    sessions = await list_sessions(db, world_id, user)
    return ListResponse(
        data=[
            SessionSummary.model_validate(session).model_copy(
                update={"number": index + 1}
            )
            for index, session in enumerate(sessions)
        ]
    )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session_route(
    world_id: uuid.UUID,
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> SessionResponse:
    """Return one session."""
    return _to_response(await get_session(db, world_id, session_id, user))


@router.patch("/{session_id}", response_model=SessionResponse)
async def update_session_route(
    world_id: uuid.UUID,
    session_id: uuid.UUID,
    data: SessionUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> SessionResponse:
    """Update a session (master only)."""
    return _to_response(await update_session(db, world_id, session_id, data, user))


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session_route(
    world_id: uuid.UUID,
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session, scope="function"),
) -> None:
    """Delete a session (master only)."""
    await delete_session(db, world_id, session_id, user)
