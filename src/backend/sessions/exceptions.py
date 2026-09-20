from fastapi import HTTPException, status


class SessionNotFoundException(HTTPException):
    def __init__(self, session_id: object):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
