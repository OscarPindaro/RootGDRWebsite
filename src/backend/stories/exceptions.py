from fastapi import HTTPException, status


class StoryNotFoundException(HTTPException):
    def __init__(self, story_id: object):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Story {story_id} not found",
        )
