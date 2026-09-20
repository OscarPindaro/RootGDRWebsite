from fastapi import HTTPException, status


class PageNotFoundException(HTTPException):
    def __init__(self, page_id: object):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Page {page_id} not found"
        )


class PageSlugConflictException(HTTPException):
    def __init__(self, slug: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A page with slug '{slug}' already exists in this world",
        )
