from fastapi import HTTPException, status


class ImageValidationError(HTTPException):
    """The upload is not an acceptable image, or is too large."""

    def __init__(self, detail: str = "The uploaded file is not a valid image"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class ImageNotFoundError(HTTPException):
    """The owner has no image to read."""

    def __init__(self, detail: str = "This item does not have an image"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
