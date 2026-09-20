from fastapi import HTTPException, status


class CharacterNotFoundException(HTTPException):
    def __init__(self, character_id: object):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Character {character_id} not found",
        )


class CharacterAccessDeniedException(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot manage this character",
        )
