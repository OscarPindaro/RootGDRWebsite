from fastapi import HTTPException, status


class DrawingNotFoundException(HTTPException):
    def __init__(self, drawing_id: object):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Drawing {drawing_id} not found",
        )


class DrawingTitleConflictException(HTTPException):
    def __init__(self, title: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A drawing named {title} already exists",
        )
