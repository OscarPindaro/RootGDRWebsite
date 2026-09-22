from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse

from .auth.dependencies import get_optional_user
from .users.schemas import User

router = APIRouter(tags=["views"])


@router.get("/")
async def index(user: User | None = Depends(get_optional_user)) -> RedirectResponse:
    """Entry point — the world list for a signed-in user, the login page otherwise.

    There is no cross-world dashboard yet: ``/worlds`` is the real product entry
    point, so ``/`` only decides which door to open.
    """
    return RedirectResponse(url="/worlds" if user else "/login", status_code=303)
