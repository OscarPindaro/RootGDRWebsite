"""Central import point that registers every model with ``Base.metadata``.

Imported by ``alembic/env.py`` and ``server.py`` so ``Base.metadata`` is fully
populated for ``create_all`` / autogenerate. Do NOT edit by hand — maintained
by ``pre_commits.model_registry``.

Keep ``db/db.py`` and ``db/__init__.py`` free of feature/registry imports to
avoid circular imports: each model module imports ``Base`` itself, so the
order of the lines below does not matter.
"""

from ..auth.models import (  # noqa: F401
    InvitationModel,
    UserAuthProviderModel,
    UserPasswordModel,
)
from ..characters.models import CharacterModel  # noqa: F401
from ..content.models import ReferenceModel  # noqa: F401
from ..files.models import FileModel  # noqa: F401
from ..images.models import ImageRevisionModel  # noqa: F401
from ..npcs.models import NpcModel  # noqa: F401
from ..pages.models import PageModel  # noqa: F401
from ..places.models import PlaceModel  # noqa: F401
from ..sessions.models import SessionModel  # noqa: F401
from ..stories.models import StoryModel  # noqa: F401
from ..tasks.models import TaskModel  # noqa: F401
from ..users.models import UserModel  # noqa: F401
from ..worlds.models import (  # noqa: F401
    WorldInviteModel,
    WorldMembershipModel,
    WorldModel,
)

__all__ = [
    "CharacterModel",
    "FileModel",
    "ImageRevisionModel",
    "InvitationModel",
    "NpcModel",
    "PageModel",
    "PlaceModel",
    "ReferenceModel",
    "SessionModel",
    "StoryModel",
    "TaskModel",
    "UserAuthProviderModel",
    "UserModel",
    "UserPasswordModel",
    "WorldInviteModel",
    "WorldMembershipModel",
    "WorldModel",
]
