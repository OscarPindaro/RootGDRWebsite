import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import get_current_admin_user, get_current_user
from ..dependencies import get_db_session
from ..schemas import ListResponse
from .exceptions import UserNotFound
from .schemas import User, UserCreate, UserResponse, UserUpdate
from .service import create_user, delete_user, get_all_users, get_user, update_user

router = APIRouter(prefix="/users", tags=["users"])


def _ensure_self_or_admin(user_id: uuid.UUID, current_user: User) -> None:
    """A user may read or change themselves; only an admin may touch others."""
    if current_user.id != user_id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own user record",
        )


@router.post(
    "/",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "User successfully created"},
        403: {"description": "Administrator role required"},
    },
)
async def create_user_endpoint(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db_session, scope="function"),
    _: User = Depends(get_current_admin_user),
):
    """Create a new user (administrator only)."""
    return await create_user(db, user_data)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    responses={
        200: {"description": "User found and returned"},
        403: {"description": "Not your own record and not an administrator"},
        404: {"description": "User not found"},
    },
)
async def get_user_endpoint(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session, scope="function"),
    current_user: User = Depends(get_current_user),
):
    """Retrieve a single user: yourself, or anyone as an administrator."""
    _ensure_self_or_admin(user_id, current_user)
    user = await get_user(db, user_id)
    if user is None:
        raise UserNotFound(user_id)
    return user


@router.get(
    "/",
    response_model=ListResponse[UserResponse],
    responses={
        200: {"description": "List of all users returned"},
        403: {"description": "Administrator role required"},
    },
)
async def get_all_users_endpoint(
    db: AsyncSession = Depends(get_db_session, scope="function"),
    _: User = Depends(get_current_admin_user),
):
    """Retrieve all users in the system (administrator only)."""
    users = await get_all_users(db)
    return ListResponse(data=users)


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    responses={
        200: {"description": "User successfully updated"},
        403: {"description": "Not your own record and not an administrator"},
        404: {"description": "User not found"},
    },
)
async def update_user_endpoint(
    user_id: uuid.UUID,
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db_session, scope="function"),
    current_user: User = Depends(get_current_user),
):
    """Update a user's name: yourself, or anyone as an administrator."""
    _ensure_self_or_admin(user_id, current_user)
    user = await update_user(db, user_id, user_data)
    if user is None:
        raise UserNotFound(user_id)
    return user


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "User successfully deleted"},
        403: {"description": "Administrator role required"},
        404: {"description": "User not found"},
    },
)
async def delete_user_endpoint(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session, scope="function"),
    _: User = Depends(get_current_admin_user),
):
    """Delete a user by their ID (administrator only)."""
    deleted = await delete_user(db, user_id)
    if not deleted:
        raise UserNotFound(user_id)
