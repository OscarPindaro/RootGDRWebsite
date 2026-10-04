from datetime import UTC, datetime, timedelta
from typing import Generic, TypeVar
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, RootModel, SecretStr

from .backup import BackupError
from .vikunja_schemas import BoardIdentity, VikunjaAccount, VikunjaSpec

T = TypeVar("T")


class BoardPage(BaseModel, Generic[T]):
    items: list[T]
    total_pages: int = Field(ge=0)


class BoardInfo(BaseModel):
    version: str
    link_sharing_enabled: bool


class BoardUser(BaseModel):
    id: int = Field(gt=0)
    username: str


class BoardProject(BaseModel):
    id: int
    title: str


class BoardAuth(BaseModel):
    token: SecretStr


class BoardToken(BaseModel):
    id: int = Field(gt=0)
    title: str
    token: SecretStr | None = None


class RouteDetail(BaseModel):
    method: str | None = None
    path: str | None = None

    model_config = ConfigDict(extra="allow")


class TokenRoutes(RootModel[dict[str, dict[str, RouteDetail]]]):
    pass


class BoardBootstrapResult(BaseModel):
    identity: BoardIdentity
    token: SecretStr


def request(
    client: httpx.Client,
    method: str,
    path: str,
    *,
    data: object = None,
    expected: int = 200,
) -> httpx.Response:
    try:
        response = client.request(method, path, json=data)
    except httpx.HTTPError:
        raise BackupError(
            "Board request failed; do not retry an ambiguous write blindly"
        ) from None
    if response.status_code != expected:
        raise BackupError(f"Board operation failed ({response.status_code})")
    return response


def login(client: httpx.Client, account: VikunjaAccount) -> None:
    auth = BoardAuth.model_validate(
        request(
            client,
            "POST",
            "/api/v2/login",
            data={
                "username": account.username,
                "password": account.password.get_secret_value(),
            },
        ).json()
    )
    client.headers["Authorization"] = "Bearer " + auth.token.get_secret_value()


def register(client: httpx.Client, account: VikunjaAccount) -> BoardUser:
    data = account.model_dump(mode="json", exclude={"password"})
    data["password"] = account.password.get_secret_value()
    return BoardUser.model_validate(
        request(client, "POST", "/api/v2/register", data=data, expected=201).json()
    )


def bootstrap_accounts(base_url: str, spec: VikunjaSpec) -> BoardBootstrapResult:
    parsed = urlsplit(base_url)
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or parsed.port is None
        or not 1024 <= parsed.port <= 65535
    ):
        raise BackupError(
            "Board bootstrap accepts only an explicitly forwarded loopback URL"
        )
    with httpx.Client(
        base_url=base_url, timeout=20, follow_redirects=False, trust_env=False
    ) as owner:
        info = BoardInfo.model_validate(request(owner, "GET", "/api/v2/info").json())
        if info.version != "v2.6.0" or info.link_sharing_enabled:
            raise BackupError("Board version does not match the pinned deployment")
        owner_user = register(owner, spec.owner)
        login(owner, spec.owner)
        tooling_user = BoardUser.model_validate(
            request(
                owner,
                "POST",
                "/api/v2/user/bots",
                data=spec.tooling.model_dump(mode="json"),
                expected=201,
            ).json()
        )
        project = BoardProject.model_validate(
            request(
                owner,
                "POST",
                "/api/v2/projects",
                data={
                    "title": spec.project_title,
                    "description": "Root GDR implementation backlog",
                },
                expected=201,
            ).json()
        )
        request(
            owner,
            "POST",
            f"/api/v2/projects/{project.id}/users",
            data={"username": spec.tooling.username, "permission": 1},
            expected=201,
        )
        with httpx.Client(
            base_url=base_url, timeout=20, follow_redirects=False, trust_env=False
        ) as tooling:
            routes = TokenRoutes.model_validate(
                request(owner, "GET", "/api/v2/routes").json()
            )
            selected = {
                "projects": [
                    "read_all",
                    "read_one",
                    "views_buckets",
                    "views_buckets_tasks",
                ],
                "tasks": ["read_all", "read_one", "create", "update"],
                "tasks_comments": ["read_all", "create"],
                "projects_views": ["read_all", "read_one"],
                "projects_views_tasks": ["read_all"],
            }
            for group, permissions in selected.items():
                if group not in routes.root or not set(permissions).issubset(
                    routes.root[group]
                ):
                    raise BackupError(
                        "Pinned board does not expose the reviewed token scopes"
                    )
            token = BoardToken.model_validate(
                request(
                    owner,
                    "POST",
                    "/api/v2/tokens",
                    data={
                        "owner_id": tooling_user.id,
                        "title": "Root GDR ticket tooling",
                        "permissions": selected,
                        "expires_at": (
                            datetime.now(UTC) + timedelta(days=365)
                        ).isoformat(),
                    },
                    expected=201,
                ).json()
            )
            if token.token is None:
                raise BackupError("Board did not return the new scoped token")
            tooling.headers["Authorization"] = (
                "Bearer " + token.token.get_secret_value()
            )
            accessible = BoardPage[BoardProject].model_validate(
                request(tooling, "GET", "/api/v2/projects").json()
            )
            if accessible.total_pages > 1 or {
                item.id for item in accessible.items if item.id > 0
            } != {project.id}:
                raise BackupError("Scoped token does not resolve only the real backlog")
        return BoardBootstrapResult(
            identity=BoardIdentity(
                version="v2.6.0",
                owner_id=owner_user.id,
                tooling_id=tooling_user.id,
                project_id=project.id,
                token_id=token.id,
            ),
            token=token.token,
        )
