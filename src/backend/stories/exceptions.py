from fastapi import HTTPException, status


class StoryNotFoundException(HTTPException):
    def __init__(self, story_id: object):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Story {story_id} not found",
        )


class StorySessionsInvalid(HTTPException):
    """The referenced sessions are not usable: unknown, duplicated or unseen.

    A user's input, not a server fault: the route answers 422 with a message
    that names the problem instead of failing the request with a 500.
    """

    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=detail,
        )
