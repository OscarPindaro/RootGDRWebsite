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


class WorldImageNotFoundException(HTTPException):
    def __init__(self, world_id: uuid.UUID):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"World {world_id} does not have an image",
        )


class ImageUploadException(HTTPException):
    def __init__(self, detail: str = "Unable to store the world image"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class SharedUserNotFoundException(HTTPException):
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more shared users do not exist",
        )
