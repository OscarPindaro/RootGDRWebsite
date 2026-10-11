import uuid

from fastapi import APIRouter, Depends, Response
from fastapi.responses import HTMLResponse
from jinjax.catalog import Catalog
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import get_current_admin_user
from ..dependencies import get_catalog_dep, get_db_session
from ..navigation import Crumb
from ..users.schemas import User
from .schemas import DrawingCreate
from .service import create_drawing, get_drawing, list_drawings, node_count_of, scene_of

router = APIRouter(tags=["drawing-views"])


def _crumbs(*extra: Crumb) -> list[Crumb]:
    return [Crumb(label="Disegni", href="/drawings"), *extra]


@router.get("/drawings", response_class=HTMLResponse)
async def drawings_page(
    catalog: Catalog = Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_admin_user),
) -> HTMLResponse:
    """The drawing list (admin only)."""
    models = await list_drawings(db, user)
    drawings = [
        {
            "id": model.id,
            "title": model.title,
            "node_count": node_count_of(model),
            "updated_at": model.updated_at,
        }
        for model in models
    ]
    return catalog.render(
        "pages.drawings.DrawingList", drawings=drawings, current_user=user
    )


@router.post("/drawings/new")
async def drawing_new_submit(
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_admin_user),
) -> Response:
    """Create a blank drawing and send the browser to it.

    The explicit action is a POST: a GET must never create a row.
    """
    model = await create_drawing(db, DrawingCreate(title="Nuovo disegno"), user)
    return Response(status_code=204, headers={"HX-Redirect": f"/drawings/{model.id}"})


@router.get("/drawings/{drawing_id}", response_class=HTMLResponse)
async def drawing_detail_page(
    drawing_id: uuid.UUID,
    catalog: Catalog = Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User = Depends(get_current_admin_user),
) -> HTMLResponse:
    """The drawing workspace (admin only)."""
    model = await get_drawing(db, drawing_id, user)
    return catalog.render(
        "pages.drawings.DrawingDetail",
        drawing=model,
        scene=scene_of(model),
        crumbs=_crumbs(Crumb(label=model.title)),
        current_user=user,
    )
