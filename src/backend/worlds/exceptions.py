import uuid

from fastapi import HTTPException, status


class WorldNotFoundException(HTTPException):
    def __init__(self, world_id: uuid.UUID):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World with id {world_id} not found",
        )


class WorldAccessDeniedException(HTTPException):
    def __init__(self, world_id: uuid.UUID):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You cannot modify world {world_id}",
        )


class SharedUserNotFoundException(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more shared users do not exist",
        )
