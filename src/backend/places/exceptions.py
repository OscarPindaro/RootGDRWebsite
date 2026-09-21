from fastapi import HTTPException, status


class PlaceNotFoundException(HTTPException):
    def __init__(self, place_id: object):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Place {place_id} not found"
        )
