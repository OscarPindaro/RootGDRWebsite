from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.dependencies import get_optional_user
from ..content.view_helpers import animal_options, shape_options, tint_options
from ..dependencies import get_catalog_dep, get_db_session
from ..navigation import ButtonGroupOption, CardItem
from ..users.schemas import User
from ..users.service import get_all_users

router = APIRouter(tags=["showcase"])


@router.get("/components", response_class=HTMLResponse)
async def showcase(
    catalog=Depends(get_catalog_dep),
    db: AsyncSession = Depends(get_db_session, scope="function"),
    user: User | None = Depends(get_optional_user),
):
    """Component showcase — living style guide."""
    users = [User.model_validate(u) for u in await get_all_users(db)]
    showcase_card = CardItem(
        name="Rugginosa",
        href="#",
        tint="p1",
        title="La Senza Tana",
        animal="gatto",
        owner_label="Giocato da Giulia",
    )
    return catalog.render(
        "pages.showcase.Showcase",
        users=users,
        current_user=user,
        showcase_card=showcase_card,
        animals=animal_options(),
        tints=tint_options(),
        shapes=shape_options(),
        button_group_views=[
            ButtonGroupOption(value="list", label="Elenco", icon="list"),
            ButtonGroupOption(value="grid", label="Griglia", icon="grid-2x2"),
            ButtonGroupOption(value="map", label="Mappa", icon="map", disabled=True),
        ],
        button_group_filters=[
            ButtonGroupOption(value="people", label="Personaggi"),
            ButtonGroupOption(value="places", label="Luoghi"),
            ButtonGroupOption(value="stories", label="Storie"),
        ],
        button_group_icons=[
            ButtonGroupOption(value="list", label="", icon="list", aria_label="Elenco"),
            ButtonGroupOption(
                value="grid", label="", icon="grid-2x2", aria_label="Griglia"
            ),
            ButtonGroupOption(value="map", label="", icon="map", aria_label="Mappa"),
        ],
        showcase_tabs=[
            ButtonGroupOption(value="write", label="Scrivi"),
            ButtonGroupOption(value="preview", label="Anteprima"),
        ],
        showcase_people=[
            ButtonGroupOption(value=user.email, label=user.email) for user in users
        ],
        roles=[
            ButtonGroupOption(value="player", label="Giocatore"),
            ButtonGroupOption(value="master", label="Master"),
        ],
    )
