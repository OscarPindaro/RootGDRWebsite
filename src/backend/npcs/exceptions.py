from fastapi import HTTPException, status


class NpcNotFoundException(HTTPException):
    def __init__(self, npc_id: object):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"NPC {npc_id} not found"
        )
